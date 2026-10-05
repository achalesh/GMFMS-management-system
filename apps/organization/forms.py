from django import forms

from .models import OrganizationSetting, SystemSetting


class SettingsForm(forms.ModelForm):
    expected_revision = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_revision"].initial = self.instance.revision
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            else:
                field.widget.attrs["class"] = "form-control"
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3


class OrganizationForm(SettingsForm):
    class Meta:
        model = OrganizationSetting
        fields = [
            "application_name",
            "short_name",
            "name",
            "name_ml",
            "network_name",
            "address",
            "phone",
            "email",
            "website",
            "signatory_name",
        ]


class SystemForm(SettingsForm):
    class Meta:
        model = SystemSetting
        fields = [
            "facilitator_id_prefix",
            "default_validity_days",
            "one_primary_per_panchayat",
            "public_directory_enabled",
            "allow_public_mobile",
            "allow_public_email",
            "allow_public_social_profiles",
            "max_upload_mb",
            "consent_version",
        ]
        help_texts = {
            "public_directory_enabled": "Public browsing is not implemented. Token-based QR verification works independently of this setting.",
            "allow_public_mobile": "An applicant's separate opt-in consent is also required before publication.",
            "allow_public_email": "An applicant's separate opt-in consent is also required before publication.",
            "allow_public_social_profiles": "An applicant's separate opt-in consent is also required before publication.",
            "one_primary_per_panchayat": "Enforced for approvals, reactivations, renewals, transfers and primary role changes.",
        }
