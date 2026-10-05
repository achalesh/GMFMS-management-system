from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.audit.services import record_event

from .models import Role, User, UserJurisdiction, UserRole
from .policies import can


@transaction.atomic
def grant_role(*, actor, user, role_code, scope, district_code="", block_code=""):
    if not can(actor, "accounts.manage"):
        raise PermissionDenied
    # Serialize edits to all role assignments for this account.
    User.objects.select_for_update().get(pk=user.pk)
    role = Role.objects.get(code=role_code)
    assignment, _ = UserRole.objects.get_or_create(
        user=user, role=role, defaults={"granted_by": actor}
    )
    assignment.active = True
    assignment.save(update_fields=["active", "updated_at"])
    from apps.locations.models import Block, District

    district = (
        District.objects.filter(
            district_code=district_code, active=True, state__active=True
        ).first()
        if district_code
        else None
    )
    block = (
        Block.objects.filter(block_code=block_code, district=district, active=True).first()
        if block_code
        else None
    )
    if scope != "STATE" and not district:
        raise ValidationError("Unknown or inactive district code.")
    if scope == "BLOCK" and not block:
        raise ValidationError("Unknown or inactive block in this district.")
    jurisdiction = UserJurisdiction(
        assignment=assignment,
        scope=scope,
        district_code=district_code,
        block_code=block_code,
        district=district,
        block=block,
    )
    jurisdiction.full_clean(validate_unique=False, validate_constraints=False)
    saved_scope, created = UserJurisdiction.objects.get_or_create(
        assignment=assignment,
        scope=scope,
        district_code=district_code,
        block_code=block_code,
        defaults={"district": district, "block": block},
    )
    if not created and (
        saved_scope.district_id != jurisdiction.district_id
        or saved_scope.block_id != jurisdiction.block_id
    ):
        saved_scope.district = district
        saved_scope.block = block
        saved_scope.save(update_fields=["district", "block", "updated_at"])
    record_event(
        actor=actor,
        action="permissions.granted",
        entity=user,
        new_values={
            "role": role_code,
            "scope": scope,
            "district": district_code,
            "block": block_code,
        },
    )
    return assignment, created


@transaction.atomic
def revoke_role(*, actor, assignment, reason):
    if not can(actor, "accounts.manage"):
        raise PermissionDenied
    if not reason.strip():
        raise ValueError("A reason is required.")
    User.objects.select_for_update().get(pk=assignment.user_id)
    assignment = UserRole.objects.select_for_update().get(pk=assignment.pk)
    assignment.active = False
    assignment.save(update_fields=["active", "updated_at"])
    record_event(
        actor=actor,
        action="permissions.revoked",
        entity=assignment.user,
        reason=reason,
        new_values={"role": assignment.role.code},
    )
