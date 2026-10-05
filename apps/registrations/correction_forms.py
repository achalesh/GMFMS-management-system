import copy

from django import forms
from django.core.exceptions import ValidationError

from .application_data import FORM_CLASSES, application_data
from .catalog import CONSENT
from .forms import UploadForm
from .uploads import validate_upload


class CorrectionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    consent_version = forms.CharField(widget=forms.HiddenInput)
    accuracy = forms.BooleanField(label=CONSENT["accuracy"])
    processing = forms.BooleanField(label=CONSENT["processing"])
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, application, ticket, policy, **kwargs):
        self.application, self.ticket, self.policy = application, ticket, policy
        initial = application_data(application)
        initial.update(consent_version=policy.consent_version)
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        source_fields = {}
        for form_class in FORM_CLASSES[1:]:
            source_fields.update(form_class.base_fields)
        source_fields.update(
            UploadForm(draft=application, max_bytes=policy.max_upload_mb * 1024 * 1024).fields
        )
        allowed = {}
        for key in ticket.allowed_fields:
            if key not in source_fields:
                raise ValidationError(
                    "A requested field is no longer available. Contact the administration for a new link."
                )
            allowed[key] = copy.deepcopy(source_fields[key])
        if "photo" in allowed:
            for key in ["crop_x", "crop_y", "crop_zoom"]:
                allowed[key] = copy.deepcopy(source_fields[key])
        self.fields = {**allowed, **self.fields}
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "choice-grid"
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise ValidationError("The correction could not be accepted.")
        if data.get("consent_version") != self.policy.consent_version:
            raise ValidationError("The consent policy changed. Reload and review it again.")
        merged = application_data(self.application)
        for key in self.ticket.allowed_fields:
            if key in data and key not in {"photo"} and not key.startswith("doc_"):
                value = data[key]
                merged[key] = (
                    list(value.values_list("pk", flat=True))
                    if hasattr(value, "values_list")
                    else value
                )
        if data.get("photo") or any(data.get(key) for key in data if key.startswith("doc_")):
            for key in self.ticket.allowed_fields:
                value = data.get(key)
                if not value or (key != "photo" and not key.startswith("doc_")):
                    continue
                try:
                    data[key] = validate_upload(
                        value,
                        max_bytes=self.policy.max_upload_mb * 1024 * 1024,
                        photo=key == "photo",
                        crop=(
                            data.get("crop_x") if data.get("crop_x") is not None else 50,
                            data.get("crop_y") if data.get("crop_y") is not None else 50,
                            data.get("crop_zoom") or 1,
                        ),
                    )
                except ValidationError as exc:
                    self.add_error(key, exc)
        self.validated = {}
        for form_class in FORM_CLASSES:
            form = form_class(merged)
            if not form.is_valid():
                for key, errors in form.errors.items():
                    if key in self.fields:
                        self.add_error(key, errors)
                    else:
                        self.add_error(
                            None,
                            f"{key.replace('_', ' ').capitalize()}: {'; '.join(errors)} Contact the administration if this field is not editable.",
                        )
            else:
                self.validated.update(form.cleaned_data)
        return data
