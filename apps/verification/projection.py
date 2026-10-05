from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.urls import reverse
from django.utils import timezone

from apps.organization.models import OrganizationSetting, SystemSetting

STATUS_LABELS = {
    "ACTIVE": "Verified Media Facilitator",
    "INACTIVE": "Facilitator Inactive",
    "SUSPENDED": "Facilitator Suspended",
    "EXPIRED": "ID Expired",
    "REPLACED": "Facilitator Replaced",
    "REVOKED": "Authorization Revoked",
}


def authorization_status(f):
    a = f.current_appointment
    if f.status not in STATUS_LABELS or not a or a.facilitator_id != f.pk:
        return "INACTIVE"
    if f.status != "ACTIVE":
        return f.status
    if a.status in {"REVOKED", "REPLACED", "SUSPENDED", "INACTIVE"}:
        return a.status
    if (
        f.valid_until < timezone.localdate()
        or a.status == "EXPIRED"
        or (a.effective_to and a.effective_to < timezone.localdate())
    ):
        return "EXPIRED"
    if a.status != "ACTIVE" or a.ended_at or a.effective_from > timezone.localdate():
        return "INACTIVE"
    p = a.panchayat
    if not (
        p.active and p.block.active and p.block.district.active and p.block.district.state.active
    ):
        return "INACTIVE"
    return "ACTIVE"


def public_organization():
    org = OrganizationSetting.objects.get(pk=1)
    return {"name": org.name, "short_name": org.short_name, "network_name": org.network_name}


def public_profile(f):
    # This is the only public serialization boundary. Never pass ORM objects into public templates.
    a = f.current_appointment
    status = authorization_status(f)
    p = a.panchayat if a else None
    dates = [f.updated_at]
    if a:
        dates.extend(
            [
                a.updated_at,
                p.updated_at,
                p.block.updated_at,
                p.block.district.updated_at,
                p.block.district.state.updated_at,
            ]
        )
    result = {
        "name": f.full_name,
        "name_ml": f.name_ml,
        "facilitator_id": f.facilitator_number,
        "role": a.get_role_display() if a else "Not appointed",
        "panchayat": p.name_en if p else "Not appointed",
        "block": p.block.name_en if p else "Not appointed",
        "district": p.block.district.name_en if p else "Not appointed",
        "status": status,
        "status_label": STATUS_LABELS[status],
        "is_authorized": status == "ACTIVE",
        "valid_until": min(f.valid_until, a.effective_to).isoformat()
        if a and a.effective_to
        else f.valid_until.isoformat(),
        "updated_at": max(dates).date().isoformat(),
        "portrait_url": reverse("verification:portrait", args=[f.verification_token]),
        "organization": public_organization(),
    }
    if status == "ACTIVE":
        policy = SystemSetting.objects.get(pk=1)
        app = f.application
        if policy.allow_public_mobile and app.public_mobile_consent and app.mobile:
            result["mobile"] = app.mobile
        if policy.allow_public_email and app.public_email_consent and app.email:
            result["email"] = app.email
        if policy.allow_public_social_profiles and app.public_social_consent:
            social = {}
            # Explicit allowlist; arbitrary JSON keys/URLs can never become published fields.
            for key in ["facebook", "instagram", "youtube", "twitter", "linkedin", "other_profile"]:
                value = (
                    app.social_profiles.get(key) if isinstance(app.social_profiles, dict) else None
                )
                if not isinstance(value, str) or len(value) > 250:
                    continue
                try:
                    URLValidator(schemes=["https", "http"])(value)
                    if urlsplit(value).username or urlsplit(value).password:
                        continue
                except (ValidationError, ValueError):
                    continue
                social[key] = value
            if social:
                result["social_profiles"] = social
    return result
