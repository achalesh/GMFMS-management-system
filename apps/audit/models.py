import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit events cannot be modified.")

    def delete(self):
        raise ValidationError("Audit events cannot be deleted.")

    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("Audit events cannot be modified.")
        return super().bulk_create(objs, **kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Audit events cannot be modified.")


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    action = models.CharField(max_length=80, db_index=True)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=64)
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp"]
        default_permissions = ("view",)
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Audit events cannot be modified.")
        kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events cannot be deleted.")
