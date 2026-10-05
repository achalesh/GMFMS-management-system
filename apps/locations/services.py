from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.policies import can
from apps.audit.services import record_event

from .models import Block, District, GramaPanchayat, State

EDITABLE = {
    State: {"name_en", "name_ml", "active"},
    District: {"name_en", "name_ml", "active", "display_order"},
    Block: {"name_en", "name_ml", "active"},
    GramaPanchayat: {"name_en", "name_ml", "active", "official_email", "office_phone"},
}


@transaction.atomic
def update_location(*, actor, model, pk, values, expected_revision, reason):
    if not can(actor, "locations.manage"):
        raise PermissionDenied
    if not reason.strip():
        raise ValidationError("A reason is required.")
    if set(values) - EDITABLE[model]:
        raise ValidationError("Unknown or immutable field.")
    instance = model.objects.select_for_update().get(pk=pk)
    if instance.revision != expected_revision:
        raise ValidationError("This location changed in another session. Reload before saving.")
    old = {key: getattr(instance, key) for key in values}
    for field, value in values.items():
        setattr(instance, field, value)
    instance.revision += 1
    instance.full_clean()
    instance.save()
    record_event(
        actor=actor,
        action="location.updated",
        entity=instance,
        old_values=old,
        new_values=values,
        reason=reason,
    )
    return instance
