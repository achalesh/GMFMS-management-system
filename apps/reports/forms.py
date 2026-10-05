from django import forms

from apps.facilitators.selectors import locations_for
from apps.locations.models import Block, District, GramaPanchayat


class ReportFilter(forms.Form):
    report = forms.ChoiceField(
        choices=[
            ("coverage", "Coverage"),
            ("progress", "Registration progress"),
            ("skills", "Facilitator skills"),
            ("equipment", "Equipment availability"),
            ("history", "Appointment history"),
            ("vacancies", "Vacant panchayats"),
            ("facilitators", "Facilitators"),
            ("applications", "Applications"),
            ("expiring", "Expiring within 30 days"),
        ],
        required=False,
    )
    district = forms.ModelChoiceField(queryset=District.objects.none(), required=False)
    block = forms.ModelChoiceField(queryset=Block.objects.none(), required=False)
    panchayat = forms.ModelChoiceField(queryset=GramaPanchayat.objects.none(), required=False)
    status = forms.ChoiceField(
        choices=[("", "All statuses")]
        + [
            (v, v.replace("_", " ").title())
            for v in [
                "ACTIVE",
                "INACTIVE",
                "SUSPENDED",
                "EXPIRED",
                "REPLACED",
                "REVOKED",
                "PENDING",
                "SUBMITTED",
                "UNDER_REVIEW",
                "CORRECTION_REQUIRED",
                "APPROVED",
                "REJECTED",
            ]
        ],
        required=False,
    )
    role = forms.ChoiceField(
        choices=[
            ("", "All roles"),
            ("PRIMARY", "Primary"),
            ("ASSISTANT", "Assistant"),
            ("ADDITIONAL", "Additional"),
        ],
        required=False,
    )
    date_field = forms.ChoiceField(
        choices=[
            ("registration", "Registration date"),
            ("approval", "Approval date"),
            ("expiry", "Expiry date"),
        ],
        required=False,
    )
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, user, capability="dashboard.view", **kwargs):
        super().__init__(*args, **kwargs)
        places = locations_for(user, capability)
        self.fields["panchayat"].queryset = places.order_by("name_en")
        self.fields["district"].queryset = (
            District.objects.filter(blocks__panchayats__in=places).distinct().order_by("name_en")
        )
        self.fields["block"].queryset = (
            Block.objects.filter(panchayats__in=places).distinct().order_by("name_en")
        )

    def clean(self):
        d = super().clean()
        district, block, p = d.get("district"), d.get("block"), d.get("panchayat")
        if (
            (district and block and block.district_id != district.pk)
            or (p and block and p.block_id != block.pk)
            or (p and district and p.block.district_id != district.pk)
        ):
            raise forms.ValidationError("Choose locations in the same hierarchy.")
        if d.get("start") and d.get("end") and d["start"] > d["end"]:
            raise forms.ValidationError("Start date must not follow end date.")
        report = d.get("report") or "coverage"
        if report in {"coverage", "vacancies"} and any(
            d.get(k) for k in ("status", "role", "start", "end")
        ):
            raise forms.ValidationError(
                "Coverage is a current snapshot. Use location filters only for coverage and vacancies."
            )
        if report in {"applications", "progress"} and (
            d.get("role") or (d.get("date_field") not in ("", "registration", None))
        ):
            raise forms.ValidationError(
                "Application reports support registration dates and application status."
            )
        allowed = (
            {"PENDING", "SUBMITTED", "UNDER_REVIEW", "CORRECTION_REQUIRED", "APPROVED", "REJECTED"}
            if report in {"applications", "progress"}
            else {"ACTIVE", "INACTIVE", "SUSPENDED", "EXPIRED", "REPLACED", "REVOKED"}
        )
        if d.get("status") and d["status"] not in allowed:
            raise forms.ValidationError("Choose a status appropriate to the report.")
        return d


class ExportForm(forms.Form):
    format = forms.ChoiceField(choices=[("xlsx", "Excel"), ("csv", "CSV"), ("pdf", "PDF")])
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 2}), strip=True)
