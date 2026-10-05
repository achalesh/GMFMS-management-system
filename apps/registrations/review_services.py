import hashlib
import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.facilitators.models import (
    Facilitator,
    FacilitatorAppointment,
    FacilitatorSequence,
    IdentityCardMetadata,
)
from apps.locations.models import GramaPanchayat
from apps.organization.models import SystemSetting

from .application_data import validate_application
from .duplicates import refresh_warnings
from .models import Application, CorrectionRequest, ReviewEvent
from .review_forms import correction_choices
from .review_selectors import can_act

ACTIONS = {
    "start_review": "applications.review",
    "request_correction": "applications.review",
    "renew_correction": "applications.review",
    "cancel_correction": "applications.review",
    "approve": "applications.approve",
    "reject": "applications.approve",
}
TRANSITIONS = {
    "start_review": ("SUBMITTED", "UNDER_REVIEW"),
    "request_correction": ("UNDER_REVIEW", "CORRECTION_REQUIRED"),
    "renew_correction": ("CORRECTION_REQUIRED", "CORRECTION_REQUIRED"),
    "cancel_correction": ("CORRECTION_REQUIRED", "UNDER_REVIEW"),
    "approve": ("UNDER_REVIEW", "APPROVED"),
    "reject": ("UNDER_REVIEW", "REJECTED"),
}


def active_primary(panchayat):
    today = timezone.localdate()
    from django.db.models import Q

    return FacilitatorAppointment.objects.filter(
        panchayat=panchayat,
        role="PRIMARY",
        status="ACTIVE",
        ended_at__isnull=True,
        facilitator__status="ACTIVE",
        facilitator__valid_until__gte=today,
        effective_from__lte=today,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))


def history(application, actor, action, old_status, reason="", changes=None):
    ReviewEvent.objects.create(
        application=application,
        actor=actor,
        action=action,
        from_status=old_status,
        to_status=application.status,
        reason=reason,
        changes=changes or {},
    )
    record_event(
        actor=actor,
        action="application." + action,
        entity=application,
        old_values={"status": old_status},
        new_values={
            "status": application.status,
            "revision": application.revision,
            "changed_fields": list((changes or {}).keys()),
        },
        reason=reason,
    )


@transaction.atomic
def review_action(
    *,
    actor,
    application_id,
    action,
    revision,
    reason="",
    allowed_fields=None,
    acknowledge_duplicates=False,
    verification_complete=False,
    appointment_role="PRIMARY",
):
    if action not in ACTIONS:
        raise ValidationError("Unknown review action.")
    # A consistent lock order also serializes approval against policy changes/submissions.
    policy = SystemSetting.objects.select_for_update().get(pk=1)
    app = Application.objects.select_for_update().get(pk=application_id)
    if not can_act(actor, app, ACTIONS[action]):
        raise PermissionDenied
    if app.revision != revision:
        raise ValidationError(
            "This application changed in another session. Reload before taking action."
        )
    expected, target = TRANSITIONS[action]
    if app.status != expected:
        raise ValidationError("This action is not available in the application's current status.")
    reason = reason.strip()
    if len(reason) > 2000:
        raise ValidationError("Keep the review reason within 2,000 characters.")
    if (
        action in {"request_correction", "renew_correction", "cancel_correction", "reject"}
        and not reason
    ):
        raise ValidationError("A reason is required for this action.")
    old = app.status
    result = {"application": app, "correction": None, "token": None}
    changes = {}
    if action == "start_review":
        app.reviewed_by = actor
        refresh_warnings(app)
    elif action in {"request_correction", "renew_correction"}:
        choices = dict(correction_choices())
        message = reason
        if action == "renew_correction":
            previous = app.correction_requests.order_by("-created_at").first()
            if not previous:
                raise ValidationError("No correction request exists.")
            allowed_fields = previous.allowed_fields
            message = previous.message
        allowed_fields = sorted(set(allowed_fields or []))
        if not allowed_fields or set(allowed_fields) - set(choices):
            raise ValidationError("Choose valid fields the applicant may correct.")
        app.correction_requests.filter(used_at__isnull=True, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        raw = secrets.token_urlsafe(32)
        ticket = CorrectionRequest.objects.create(
            application=app,
            requested_by=actor,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            allowed_fields=allowed_fields,
            message=message,
            expires_at=timezone.now() + timedelta(hours=48),
        )
        result.update(correction=ticket, token=raw)
    elif action == "cancel_correction":
        app.correction_requests.filter(used_at__isnull=True, revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
    elif action == "approve":
        if appointment_role not in FacilitatorAppointment.Role.values:
            raise ValidationError("Choose a valid appointment role.")
        if not verification_complete:
            raise ValidationError(
                "Confirm that the application details, documents and consent have been verified."
            )
        validate_application(app)
        matches = refresh_warnings(app)
        if matches and (not acknowledge_duplicates or not reason):
            raise ValidationError(
                "Review duplicate warnings, acknowledge them and explain your approval decision."
            )
        panchayat = GramaPanchayat.objects.select_for_update().get(pk=app.panchayat_id)
        if (
            appointment_role == "PRIMARY"
            and policy.one_primary_per_panchayat
            and active_primary(panchayat).exists()
        ):
            raise ValidationError(
                "This Panchayat already has an active primary facilitator. Use the replacement action in the facilitator registry."
            )
        district = panchayat.block.district
        sequence, _ = FacilitatorSequence.objects.get_or_create(district=district)
        sequence.value += 1
        sequence.save()
        valid_until = timezone.localdate() + timedelta(days=policy.default_validity_days)
        facilitator = Facilitator.objects.create(
            application=app,
            facilitator_number=f"{policy.facilitator_id_prefix}-{district.district_code}-{sequence.value:04d}",
            full_name=app.full_name,
            name_ml=app.name_ml,
            approved_by=actor,
            valid_until=valid_until,
        )
        appointment = FacilitatorAppointment.objects.create(
            role=appointment_role,
            facilitator=facilitator,
            panchayat=panchayat,
            approved_by=actor,
            effective_to=valid_until,
        )
        facilitator.current_appointment = appointment
        facilitator.save(update_fields=["current_appointment"])
        from apps.facilitators.services import record_history

        record_history(facilitator, actor, "approved", "", reason or "Application approved.")
        IdentityCardMetadata.objects.create(facilitator=facilitator, valid_until=valid_until)
        app.decided_by = actor
        app.decided_at = timezone.now()
        changes = {
            "facilitator_number": {"old": None, "new": facilitator.facilitator_number},
            "duplicate_warnings_reviewed": {"old": None, "new": len(matches)},
        }
    elif action == "reject":
        app.decided_by = actor
        app.decided_at = timezone.now()
    app.status = target
    app.revision += 1
    app.save()
    history(app, actor, action, old, reason, changes)
    return result
