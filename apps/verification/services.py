import hashlib
import secrets
from io import BytesIO
from urllib.parse import urlsplit

import qrcode
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.urls import reverse

from apps.audit.services import record_event
from apps.facilitators.models import Facilitator
from apps.facilitators.selectors import permitted
from apps.organization.models import SystemSetting

from .models import VerificationTokenHistory


def verification_url(f):
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    parsed = urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or len(base) > 300
    ):
        raise ValidationError(
            "Configure PUBLIC_BASE_URL as the application origin without credentials, a path, query or fragment."
        )
    return base + reverse("verification:verify", args=[f.verification_token])


def qr_png(url):
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    code.add_data(url)
    code.make(fit=True)
    buffer = BytesIO()
    code.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return buffer.getvalue()


@transaction.atomic
def rotate_token(*, actor, facilitator_id, revision, reason, confirmed):
    SystemSetting.objects.select_for_update().get(pk=1)
    f = Facilitator.objects.select_for_update().get(pk=facilitator_id)
    if not f.current_appointment_id or not permitted(actor, f.current_appointment.panchayat):
        raise PermissionDenied
    if revision != f.revision:
        raise ValidationError(
            "This identity changed. Reload before rotating its verification token."
        )
    reason = reason.strip()
    if not reason or len(reason) > 2000 or not confirmed:
        raise ValidationError(
            "Provide a reason and confirm that all existing QR links will stop working."
        )
    old_digest = hashlib.sha256(f.verification_token.encode()).hexdigest()
    f.verification_token = secrets.token_urlsafe(32)
    f.revision += 1
    f.save(update_fields=["verification_token", "revision", "updated_at"])
    new_digest = hashlib.sha256(f.verification_token.encode()).hexdigest()
    VerificationTokenHistory.objects.create(
        facilitator=f,
        previous_digest=old_digest,
        replacement_digest=new_digest,
        changed_by=actor,
        reason=reason,
    )
    record_event(
        actor=actor,
        action="verification.token_rotated",
        entity=f,
        old_values={"token_digest": old_digest},
        new_values={"token_digest": new_digest, "revision": f.revision},
        reason=reason,
    )
    return f
