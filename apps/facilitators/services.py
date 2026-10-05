from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.locations.models import GramaPanchayat
from apps.organization.models import SystemSetting

from .models import Facilitator, FacilitatorAppointment, FacilitatorStatusHistory
from .selectors import permitted, primary_appointments

ACTIONS = {
    "details": "Edit appointment details",
    "suspend": "Suspend",
    "inactivate": "Mark inactive",
    "resign": "Record resignation",
    "revoke": "Revoke",
    "reactivate": "Reactivate",
    "renew": "Renew validity",
    "transfer": "Transfer Panchayat",
    "role": "Change appointment role",
    "replace": "Replace facilitator",
}


def snapshot(f):
    a = f.current_appointment
    return {
        "status": f.status,
        "valid_until": f.valid_until.isoformat(),
        "revision": f.revision,
        "appointment": str(a.pk),
        "panchayat": a.panchayat_id,
        "role": a.role,
        "appointment_reference": a.appointment_reference,
        "notes": a.notes,
    }


def record_history(f, actor, action, previous_status, reason, changes=None):
    FacilitatorStatusHistory.objects.create(
        facilitator=f,
        appointment=f.current_appointment,
        action=action,
        previous_status=previous_status,
        new_status=f.status,
        reason=reason,
        changed_by=actor,
        changes=changes or {},
    )
    record_event(
        actor=actor,
        action="facilitator." + action,
        entity=f,
        old_values=(changes or {}).get("old", {"status": previous_status}),
        new_values=(changes or {}).get("new", {"status": f.status}),
        reason=reason,
    )


def require_location(panchayat):
    if not (
        panchayat.active
        and panchayat.block.active
        and panchayat.block.district.active
        and panchayat.block.district.state.active
    ):
        raise ValidationError("The Panchayat and all parent locations must be active.")


def check_primary(f, panchayat, role, policy):
    if (
        policy.one_primary_per_panchayat
        and role == "PRIMARY"
        and primary_appointments().filter(panchayat=panchayat).exclude(facilitator=f).exists()
    ):
        raise ValidationError("This Panchayat already has an active primary facilitator.")


def close_appointment(a, status, reason):
    a.status = status
    a.effective_to = min(a.effective_to or timezone.localdate(), timezone.localdate())
    a.ended_at = timezone.now()
    a.end_reason = reason
    a.save()


def new_appointment(f, actor, panchayat, role):
    f.current_appointment = FacilitatorAppointment.objects.create(
        facilitator=f, panchayat=panchayat, role=role, approved_by=actor, effective_to=f.valid_until
    )


@transaction.atomic
def registry_action(
    *,
    actor,
    facilitator_id,
    action,
    revision,
    reason,
    appointment_reference="",
    notes="",
    valid_until=None,
    panchayat_id=None,
    role=None,
    replacement_id=None,
    application_revision=None,
    verification_complete=False,
    acknowledge_duplicates=False,
):
    if action not in ACTIONS:
        raise ValidationError("Unknown registry action.")
    policy = SystemSetting.objects.select_for_update().get(pk=1)
    f = Facilitator.objects.select_for_update().get(pk=facilitator_id)
    if not f.current_appointment_id:
        raise ValidationError(
            "This record has no current appointment; contact a system administrator."
        )
    a = (
        FacilitatorAppointment.objects.select_for_update()
        .select_related("panchayat__block__district__state")
        .get(pk=f.current_appointment_id)
    )
    f.current_appointment = a
    if not permitted(actor, a.panchayat):
        raise PermissionDenied
    if f.revision != revision:
        raise ValidationError(
            "This facilitator changed in another session. Reload before continuing."
        )
    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise ValidationError("Provide a reason of 1 to 2,000 characters.")
    old = snapshot(f)
    today = timezone.localdate()
    if f.status in {"REVOKED", "REPLACED"}:
        raise ValidationError(
            "Revoked and replaced identities are historical and cannot be reactivated or edited."
        )
    if action == "details":
        if a.ended_at:
            raise ValidationError("Historical appointment details cannot be edited.")
        appointment_reference, notes = appointment_reference.strip(), notes.strip()
        if len(appointment_reference) > 150 or len(notes) > 2000:
            raise ValidationError("Appointment reference or notes exceed the allowed length.")
        if (a.appointment_reference, a.notes) == (appointment_reference, notes):
            raise ValidationError("Change the reference or notes before saving.")
        a.appointment_reference, a.notes = appointment_reference, notes
        a.save()
    elif action in {"suspend", "inactivate", "resign", "revoke"}:
        target = {
            "suspend": "SUSPENDED",
            "inactivate": "INACTIVE",
            "resign": "INACTIVE",
            "revoke": "REVOKED",
        }[action]
        if f.status == target and action != "resign":
            raise ValidationError("The facilitator already has this status.")
        if a.ended_at and action != "revoke":
            raise ValidationError(
                "This appointment has ended. Reactivate with a new appointment first."
            )
        f.status = target
        if action in {"resign", "revoke"}:
            if not a.ended_at:
                close_appointment(a, target, reason)
        else:
            a.status = target
            a.save()
    elif action == "renew":
        if not isinstance(valid_until, date) or valid_until <= max(today, f.valid_until):
            raise ValidationError(
                "New validity must be later than today and the existing expiry date."
            )
        if (valid_until - today).days > 3650:
            raise ValidationError("Validity cannot exceed ten years from today.")
        f.valid_until = valid_until
        if not a.ended_at:
            a.effective_to = valid_until
            # Renewal of an expired active appointment restores authorization, so check conflicts.
            if f.status in {"ACTIVE", "EXPIRED"}:
                require_location(a.panchayat)
                check_primary(f, a.panchayat, a.role, policy)
                f.status = a.status = "ACTIVE"
            a.save()
    elif action == "reactivate":
        if f.effective_status == "ACTIVE":
            raise ValidationError("The facilitator is already active.")
        if f.valid_until < today:
            raise ValidationError("Renew the expired validity before reactivation.")
        require_location(a.panchayat)
        check_primary(f, a.panchayat, a.role, policy)
        f.status = "ACTIVE"
        if a.ended_at:
            new_appointment(f, actor, a.panchayat, a.role)
        else:
            a.status = "ACTIVE"
            a.save()
    elif action in {"transfer", "role"}:
        if f.effective_status != "ACTIVE" or a.ended_at:
            raise ValidationError(
                "Only an active current appointment can be transferred or change role."
            )
        target = (
            GramaPanchayat.objects.select_for_update()
            .select_related("block__district__state")
            .get(pk=panchayat_id)
            if action == "transfer"
            else a.panchayat
        )
        if not permitted(actor, target):
            raise PermissionDenied
        require_location(target)
        new_role = role if action == "role" else a.role
        if new_role not in FacilitatorAppointment.Role.values:
            raise ValidationError("Choose a valid appointment role.")
        if target.pk == a.panchayat_id and new_role == a.role:
            raise ValidationError("Choose a different Panchayat or appointment role.")
        check_primary(f, target, new_role, policy)
        close_appointment(a, "INACTIVE", reason)
        new_appointment(f, actor, target, new_role)
    elif action == "replace":
        from apps.registrations.models import Application
        from apps.registrations.review_services import review_action

        if a.role != "PRIMARY" or a.ended_at:
            raise ValidationError("Replacement requires a current primary appointment.")
        candidate = Application.objects.select_for_update().get(pk=replacement_id)
        if candidate.panchayat_id != a.panchayat_id or candidate.status != "UNDER_REVIEW":
            raise ValidationError("Select an application under review for the same Panchayat.")
        # The approval service checks its own capability and all original validation requirements.
        close_appointment(a, "REPLACED", reason)
        f.status = "REPLACED"
        f.save()
        result = review_action(
            actor=actor,
            application_id=candidate.pk,
            action="approve",
            revision=application_revision,
            reason=reason,
            verification_complete=verification_complete,
            acknowledge_duplicates=acknowledge_duplicates,
        )
        successor = result["application"].facilitator
        old["replacement_facilitator"] = None
    f.revision += 1
    f.save()
    changes = {"old": old, "new": snapshot(f)}
    if action == "replace":
        changes["new"]["replacement_facilitator"] = successor.facilitator_number
    record_history(f, actor, action, old["status"], reason, changes)
    return f


@transaction.atomic
def expire_identities():
    SystemSetting.objects.select_for_update().get(pk=1)
    count = 0
    for f in Facilitator.objects.select_for_update().filter(
        status="ACTIVE", valid_until__lt=timezone.localdate()
    ):
        if not f.current_appointment_id:
            continue
        old = snapshot(f)
        f.status = "EXPIRED"
        f.revision += 1
        f.save()
        a = f.current_appointment
        if not a.ended_at:
            a.status = "EXPIRED"
            a.save()
        record_history(
            f,
            None,
            "expired",
            old["status"],
            "Authorization validity elapsed.",
            {"old": old, "new": snapshot(f)},
        )
        count += 1
    return count
