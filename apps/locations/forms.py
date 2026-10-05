from django import forms

from .models import Block, District, GramaPanchayat, State


class LocationEditForm(forms.ModelForm):
    expected_revision = forms.IntegerField(widget=forms.HiddenInput)
    reason = forms.CharField(
        max_length=500, help_text="Explain the correction or status change for the audit trail."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["expected_revision"].initial = self.instance.revision
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )


class StateForm(LocationEditForm):
    class Meta:
        model = State
        fields = ["name_en", "name_ml", "active"]


class DistrictForm(LocationEditForm):
    class Meta:
        model = District
        fields = ["name_en", "name_ml", "display_order", "active"]


class BlockForm(LocationEditForm):
    class Meta:
        model = Block
        fields = ["name_en", "name_ml", "active"]


class PanchayatForm(LocationEditForm):
    class Meta:
        model = GramaPanchayat
        fields = ["name_en", "name_ml", "official_email", "office_phone", "active"]


class ImportForm(forms.Form):
    file = forms.FileField(
        label="CSV or XLSX file",
        help_text="Maximum 5 MB, 5,000 rows. Use the downloadable column template.",
    )
    source = forms.CharField(
        max_length=500, help_text="Official source URL or reference for this dataset."
    )
    update_existing = forms.BooleanField(
        required=False,
        label="Update existing records",
        help_text="Codes and parent relationships cannot change. Omitted records are never deleted.",
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        label="Validate only (dry run)",
        help_text="Check the entire file without saving any changes.",
    )
