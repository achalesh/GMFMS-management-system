from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.audit.models import AppendOnlyQuerySet


class VerificationTokenHistory(models.Model):
    facilitator = models.ForeignKey(
        "facilitators.Facilitator", on_delete=models.PROTECT, related_name="token_history"
    )
    previous_digest = models.CharField(max_length=64)
    replacement_digest = models.CharField(max_length=64)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(max_length=2000)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["pk"]
        default_permissions = ("view",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Verification token history cannot be modified.")
        kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Verification token history cannot be deleted.")
