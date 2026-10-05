from django import forms
from django.core.exceptions import ValidationError

from apps.facilitators.models import FacilitatorAppointment

from .forms import EquipmentForm, PersonalForm, ProfessionalForm
from .models import DocumentType


def correction_choices():
    choices = []
    for form_class in [PersonalForm, ProfessionalForm, EquipmentForm]:
        for key, field in form_class.base_fields.items():
            if key != "revision":
                choices.append((key, field.label or key.replace("_", " ").capitalize()))
    choices.append(("photo", "Profile photograph"))
    choices.extend(
        ("doc_" + kind.code, kind.name) for kind in DocumentType.objects.filter(active=True)
    )
    return choices


class ActionForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    reason = forms.CharField(
        max_length=2000,
        required=False,
        label="Review note / reason",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    acknowledge_duplicates = forms.BooleanField(
        required=False,
        label="I have reviewed the duplicate warnings and explained the decision above.",
    )
    verification_complete = forms.BooleanField(
        required=False,
        label="I have verified the application details, documents and recorded consent.",
    )
    allowed_fields = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Fields the applicant may correct",
    )

    def __init__(self, *args, action, **kwargs):
        self.action = action
        super().__init__(*args, **kwargs)
        self.fields["allowed_fields"].choices = correction_choices()
        if action != "request_correction":
            self.fields.pop("allowed_fields")
        if action == "approve":
            self.fields["appointment_role"] = forms.ChoiceField(
                choices=FacilitatorAppointment.Role.choices,
                initial="PRIMARY",
                required=False,
                label="Appointment role",
            )
        if action != "approve":
            self.fields.pop("acknowledge_duplicates")
            self.fields.pop("verification_complete")
        if action in {"request_correction", "reject", "renew_correction", "cancel_correction"}:
            self.fields["reason"].required = True
        if action == "request_correction":
            self.fields["reason"].label = "Correction instructions for the applicant"
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs["class"] = "choice-grid"
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean(self):
        data = super().clean()
        if self.action == "approve":
            data["appointment_role"] = data.get("appointment_role") or "PRIMARY"
        if self.action == "request_correction" and not data.get("allowed_fields"):
            raise ValidationError("Select at least one field the applicant may correct.")
        return data
