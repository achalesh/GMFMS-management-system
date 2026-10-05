import re
from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from apps.locations.selectors import active_blocks, active_districts, active_panchayats

from .catalog import CONSENT
from .models import DocumentType, Equipment, Language, Skill
from .uploads import validate_upload


def mobile_number(value):
    value = re.sub(r"[\s()-]", "", value)
    if value.startswith("+91"):
        value = value[3:]
    if not re.fullmatch(r"[6-9][0-9]{9}", value):
        raise ValidationError("Enter a valid 10-digit Indian mobile number (optional +91 prefix).")
    return value


class StepForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput, min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "choice-grid"
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3


class LocationForm(StepForm):
    district = forms.ModelChoiceField(queryset=active_districts())
    block = forms.ModelChoiceField(queryset=active_blocks().none())
    panchayat = forms.ModelChoiceField(queryset=active_panchayats().none(), label="Grama Panchayat")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        values = self.data if self.is_bound else self.initial
        district, block = str(values.get("district", "")), str(values.get("block", ""))
        if district.isascii() and district.isdigit() and len(district) <= 10:
            self.fields["block"].queryset = active_blocks().filter(district_id=int(district))
        if block.isascii() and block.isdigit() and len(block) <= 10:
            self.fields["panchayat"].queryset = active_panchayats().filter(
                block_id=int(block), block__in=self.fields["block"].queryset
            )

    def clean(self):
        data = super().clean()
        if (
            data.get("block")
            and data.get("district")
            and data["block"].district_id != data["district"].pk
        ):
            self.add_error("block", "Choose a block in your selected district.")
        if (
            data.get("panchayat")
            and data.get("block")
            and data["panchayat"].block_id != data["block"].pk
        ):
            self.add_error("panchayat", "Choose a Panchayat in your selected block.")
        return data


class PersonalForm(StepForm):
    full_name = forms.CharField(
        max_length=150, label="Full name", widget=forms.TextInput(attrs={"autocomplete": "name"})
    )
    name_ml = forms.CharField(max_length=180, required=False, label="Name in Malayalam")
    gender = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Prefer not to say"),
            ("female", "Female"),
            ("male", "Male"),
            ("other", "Other"),
        ],
    )
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    mobile = forms.CharField(
        max_length=20,
        label="Mobile number",
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
    )
    whatsapp = forms.CharField(
        max_length=20,
        required=False,
        label="WhatsApp number",
        help_text="Leave blank to use your mobile number.",
    )
    email = forms.EmailField(
        required=False, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    address = forms.CharField(max_length=1500, label="Residential address", widget=forms.Textarea)
    pin_code = forms.RegexField(
        r"^[1-9][0-9]{5}$",
        label="PIN code",
        max_length=6,
        widget=forms.TextInput(attrs={"inputmode": "numeric"}),
        error_messages={"invalid": "Enter a six-digit Indian PIN code."},
    )
    emergency_name = forms.CharField(max_length=150, required=False, label="Emergency contact name")
    emergency_relationship = forms.CharField(max_length=80, required=False, label="Relationship")
    emergency_mobile = forms.CharField(
        max_length=20, required=False, label="Emergency mobile number"
    )

    def clean_mobile(self):
        return mobile_number(self.cleaned_data["mobile"])

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean_date_of_birth(self):
        value = self.cleaned_data["date_of_birth"]
        if value and (value > date.today() or value.year < date.today().year - 120):
            raise ValidationError("Enter a valid date of birth in the past.")
        return value

    def clean(self):
        data = super().clean()
        for key in ["whatsapp", "emergency_mobile"]:
            if data.get(key):
                try:
                    data[key] = mobile_number(data[key])
                except ValidationError as exc:
                    self.add_error(key, exc)
        if not data.get("whatsapp"):
            data["whatsapp"] = data.get("mobile", "")
        emergency = [
            data.get(key)
            for key in ["emergency_name", "emergency_relationship", "emergency_mobile"]
        ]
        if any(emergency) and not all(emergency):
            raise ValidationError(
                "Complete all three emergency contact fields, or leave them all blank."
            )
        return data


class ProfessionalForm(StepForm):
    occupation = forms.CharField(max_length=150, required=False)
    qualification = forms.CharField(
        max_length=180, required=False, label="Educational qualification"
    )
    current_organization = forms.CharField(max_length=180, required=False)
    designation = forms.CharField(max_length=150, required=False)
    media_experience = forms.CharField(max_length=2000, required=False, widget=forms.Textarea)
    years_experience = forms.IntegerField(
        min_value=0, max_value=80, initial=0, label="Years of media experience"
    )
    skills = forms.ModelMultipleChoiceField(
        queryset=Skill.objects.filter(active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    other_skill = forms.CharField(max_length=200, required=False, label="Other skill")
    languages = forms.ModelMultipleChoiceField(
        queryset=Language.objects.filter(active=True),
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )
    other_language = forms.CharField(max_length=100, required=False, label="Other language")

    def clean(self):
        data = super().clean()
        for key, other in [("skills", "other_skill"), ("languages", "other_language")]:
            if any(item.code == "other" for item in data.get(key, [])) and not data.get(other):
                self.add_error(other, "Please specify your selection.")
        return data


class EquipmentForm(StepForm):
    equipment = forms.ModelMultipleChoiceField(
        queryset=Equipment.objects.filter(active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Equipment you can access",
    )
    other_equipment = forms.CharField(max_length=200, required=False)
    facebook = forms.URLField(required=False, max_length=250)
    instagram = forms.URLField(required=False, max_length=250)
    youtube = forms.URLField(required=False, max_length=250)
    twitter = forms.URLField(required=False, max_length=250, label="X / Twitter")
    linkedin = forms.URLField(required=False, max_length=250)
    other_profile = forms.URLField(required=False, max_length=250, label="Other media profile")

    def clean(self):
        data = super().clean()
        if any(item.code == "other" for item in data.get("equipment", [])) and not data.get(
            "other_equipment"
        ):
            self.add_error("other_equipment", "Please specify your equipment.")
        for key in ["facebook", "instagram", "youtube", "twitter", "linkedin", "other_profile"]:
            if data.get(key):
                try:
                    URLValidator(schemes=["http", "https"])(data[key])
                except ValidationError:
                    self.add_error(key, "Use an http or https profile URL.")
        return data


class UploadForm(StepForm):
    photo = forms.FileField(
        required=False,
        label="Profile photograph",
        help_text="JPG, JPEG or PNG. A photograph is required; use the crop controls after choosing a file.",
        widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png"}),
    )
    crop_x = forms.FloatField(
        min_value=0, max_value=100, initial=50, required=False, widget=forms.HiddenInput
    )
    crop_y = forms.FloatField(
        min_value=0, max_value=100, initial=50, required=False, widget=forms.HiddenInput
    )
    crop_zoom = forms.FloatField(
        min_value=1, max_value=3, initial=1, required=False, widget=forms.HiddenInput
    )

    def __init__(self, *args, draft, max_bytes, **kwargs):
        self.draft, self.max_bytes = draft, max_bytes
        super().__init__(*args, **kwargs)
        self.existing = set(draft.uploads.values_list("slot", flat=True))
        for kind in DocumentType.objects.filter(active=True):
            self.fields["doc_" + kind.code] = forms.FileField(
                required=False,
                label=kind.name + (" (required)" if kind.required else ""),
                help_text=kind.instructions or "Optional. PDF, JPG, JPEG or PNG.",
                widget=forms.FileInput(
                    attrs={"accept": ".pdf,.jpg,.jpeg,.png", "class": "form-control"}
                ),
            )

        for slot in sorted(self.existing - {"photo"}):
            kind = DocumentType.objects.filter(code=slot.removeprefix("doc_")).first()
            if not kind or not (kind.active and kind.required):
                self.fields["remove_" + slot] = forms.BooleanField(
                    required=False,
                    label="Remove uploaded " + (kind.name if kind else "document"),
                    widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                )

    def clean(self):
        data = super().clean()
        if not data.get("photo") and "photo" not in self.existing:
            self.add_error("photo", "Upload a profile photograph.")
        for kind in DocumentType.objects.filter(active=True, required=True):
            key = "doc_" + kind.code
            if not data.get(key) and key not in self.existing:
                self.add_error(key, "This document is required.")
        for key, value in list(data.items()):
            if value and (key == "photo" or key.startswith("doc_")):
                try:
                    data[key] = validate_upload(
                        value,
                        max_bytes=self.max_bytes,
                        photo=key == "photo",
                        crop=(
                            data.get("crop_x") if data.get("crop_x") is not None else 50,
                            data.get("crop_y") if data.get("crop_y") is not None else 50,
                            data.get("crop_zoom") or 1,
                        ),
                    )
                except ValidationError as exc:
                    self.add_error(key, exc)
        return data


class ConsentForm(StepForm):
    accuracy = forms.BooleanField(label=CONSENT["accuracy"])
    processing = forms.BooleanField(label=CONSENT["processing"])
    public_mobile = forms.BooleanField(required=False, label=CONSENT["mobile"])
    public_email = forms.BooleanField(required=False, label=CONSENT["email"])
    public_social = forms.BooleanField(required=False, label=CONSENT["social"])
    consent_version = forms.CharField(widget=forms.HiddenInput)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if self.cleaned_data["website"]:
            raise ValidationError("The submission could not be accepted.")
        return ""
