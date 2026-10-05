from django import forms

from apps.locations.models import Block, District
from apps.registrations.review_selectors import applications_for

from .models import FacilitatorAppointment
from .selectors import locations_for


def style(form):
    for field in form.fields.values():
        if not isinstance(field.widget, (forms.CheckboxInput, forms.HiddenInput)):
            field.widget.attrs["class"] = "form-control"


class RegistryFilter(forms.Form):
    q = forms.CharField(required=False, max_length=150, label="ID, name, application or location")
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")]
        + [
            (s, s.title())
            for s in ["ACTIVE", "INACTIVE", "SUSPENDED", "EXPIRED", "REPLACED", "REVOKED"]
        ],
    )
    role = forms.ChoiceField(
        required=False, choices=[("", "All roles")] + list(FacilitatorAppointment.Role.choices)
    )
    district = forms.ModelChoiceField(queryset=District.objects.none(), required=False)
    block = forms.ModelChoiceField(queryset=Block.objects.none(), required=False)
    panchayat = forms.ModelChoiceField(queryset=None, required=False)
    approval_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    approval_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    registered_from = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    registered_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    expiry_after = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    expiry_before = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        places = locations_for(user)
        self.fields["panchayat"].queryset = places
        self.fields["district"].queryset = District.objects.filter(
            pk__in=places.values("block__district_id")
        )
        self.fields["block"].queryset = Block.objects.filter(pk__in=places.values("block_id"))
        style(self)

    def clean(self):
        data = super().clean()
        start, end = data.get("approval_from"), data.get("approval_to")
        if start and end and start > end:
            raise forms.ValidationError("Approval start date must precede end date.")
        return data


class RegistryActionForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    reason = forms.CharField(
        max_length=2000, widget=forms.Textarea(attrs={"rows": 3}), label="Reason"
    )

    def __init__(self, *args, action, facilitator, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["revision"].initial = facilitator.revision
        if action == "details":
            self.fields["appointment_reference"] = forms.CharField(
                required=False,
                max_length=150,
                initial=facilitator.current_appointment.appointment_reference,
            )
            self.fields["notes"] = forms.CharField(
                required=False,
                max_length=2000,
                widget=forms.Textarea(attrs={"rows": 3}),
                initial=facilitator.current_appointment.notes,
                label="Private appointment notes",
            )
        elif action == "renew":
            self.fields["valid_until"] = forms.DateField(
                widget=forms.DateInput(attrs={"type": "date"}), label="New valid-until date"
            )
        elif action == "transfer":
            self.fields["panchayat"] = forms.ModelChoiceField(
                queryset=locations_for(user, "facilitators.change")
                .filter(active=True, block__active=True, block__district__active=True)
                .exclude(pk=facilitator.current_appointment.panchayat_id),
                label="Destination Panchayat",
            )
        elif action == "role":
            self.fields["role"] = forms.ChoiceField(
                choices=FacilitatorAppointment.Role.choices,
                initial=facilitator.current_appointment.role,
            )
        elif action == "replace":
            candidates = applications_for(user).filter(
                panchayat=facilitator.current_appointment.panchayat, status="UNDER_REVIEW"
            )
            self.candidates = {f"{app.pk}:{app.revision}": app for app in candidates}
            self.fields["replacement"] = forms.ChoiceField(
                choices=[("", "Select a reviewed application")]
                + [
                    (key, f"{app.application_number} — {app.full_name}")
                    for key, app in self.candidates.items()
                ],
                label="Incoming application",
                help_text="Review the application and its documents before confirming. If it changes, reload this page.",
            )
            self.fields["verification_complete"] = forms.BooleanField(
                label="I verified the incoming application, documents and consent"
            )
            self.fields["acknowledge_duplicates"] = forms.BooleanField(
                required=False,
                label="I reviewed duplicate warnings and explained the decision above",
            )
        style(self)

    def clean(self):
        data = super().clean()
        if data.get("replacement"):
            app = self.candidates[data["replacement"]]
            data["replacement"] = app
            data["application_revision"] = app.revision
        return data
