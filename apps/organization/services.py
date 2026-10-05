from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.policies import can
from apps.audit.services import record_event

from .forms import OrganizationForm, SystemForm
from .models import OrganizationSetting, SystemSetting


@transaction.atomic
def update_settings(*, actor, model, values, expected_revision):
    contracts = {
        OrganizationSetting: ("organization.change", OrganizationForm.Meta.fields),
        SystemSetting: ("system.change", SystemForm.Meta.fields),
    }
    capability, allowed_fields = contracts[model]
    if not can(actor, capability):
        raise PermissionDenied
    instance = model.objects.select_for_update().get(pk=1)
    if instance.revision != expected_revision:
        raise ValidationError(
            "These settings changed in another session. Reload this page before saving."
        )
    if set(values) - set(allowed_fields):
        raise ValidationError("Unknown or protected settings fields.")
    old = {key: getattr(instance, key) for key in values}
    for key, value in values.items():
        setattr(instance, key, value)
    instance.revision += 1
    instance.full_clean()
    instance.save()
    record_event(
        actor=actor,
        action=f"{model._meta.model_name}.updated",
        entity=instance,
        old_values=old,
        new_values=values,
    )
    return instance
