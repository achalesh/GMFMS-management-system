import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.audit.models import AppendOnlyQuerySet
from apps.common.models import TimestampedModel


def verification_token():
    return secrets.token_urlsafe(32)


class FacilitatorSequence(models.Model):
    district = models.OneToOneField(
        "locations.District", primary_key=True, on_delete=models.PROTECT
    )
    value = models.PositiveIntegerField(default=0)


class Facilitator(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        "registrations.Application", on_delete=models.PROTECT, related_name="facilitator"
    )
    facilitator_number = models.CharField(max_length=50, unique=True)
    revision = models.PositiveIntegerField(default=1)
    current_appointment = models.OneToOneField(
        "FacilitatorAppointment",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_for",
    )
    full_name = models.CharField(max_length=150)
    name_ml = models.CharField(max_length=180, blank=True)
    status = models.CharField(
        max_length=20,
        default="ACTIVE",
        choices=[
            (item, item.title())
            for item in ["ACTIVE", "INACTIVE", "SUSPENDED", "EXPIRED", "REPLACED", "REVOKED"]
        ],
    )
    verification_token = models.CharField(
        max_length=64, unique=True, default=verification_token, editable=False
    )
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    approved_at = models.DateTimeField(default=timezone.now)
    valid_until = models.DateField()

    @property
    def effective_status(self):
        if self.status == "ACTIVE" and self.valid_until < timezone.localdate():
            return "EXPIRED"
        return self.status

    def __str__(self):
        return self.facilitator_number


class FacilitatorAppointment(TimestampedModel):
    class Role(models.TextChoices):
        PRIMARY = "PRIMARY", "Primary"
        ASSISTANT = "ASSISTANT", "Assistant"
        ADDITIONAL = "ADDITIONAL", "Additional"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facilitator = models.ForeignKey(
        Facilitator, on_delete=models.PROTECT, related_name="appointments"
    )
    panchayat = models.ForeignKey(
        "locations.GramaPanchayat", on_delete=models.PROTECT, related_name="appointments"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PRIMARY)
    status = models.CharField(
        max_length=20,
        default="ACTIVE",
        choices=[
            (item, item.title())
            for item in ["ACTIVE", "INACTIVE", "SUSPENDED", "EXPIRED", "REPLACED", "REVOKED"]
        ],
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.TextField(blank=True, max_length=2000)
    approved_at = models.DateTimeField(default=timezone.now)
    appointment_reference = models.CharField(max_length=150, blank=True)
    notes = models.TextField(max_length=2000, blank=True)
    appointment_date = models.DateField(default=timezone.localdate)
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    @property
    def effective_status(self):
        if (
            not self.ended_at
            and self.status == "ACTIVE"
            and (
                self.facilitator.valid_until < timezone.localdate()
                or (self.effective_to and self.effective_to < timezone.localdate())
            )
        ):
            return "EXPIRED"
        return self.status

    class Meta:
        indexes = [models.Index(fields=["panchayat", "role", "status"])]


class IdentityCardMetadata(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facilitator = models.OneToOneField(
        Facilitator, on_delete=models.PROTECT, related_name="initial_card"
    )
    status = models.CharField(max_length=20, default="PENDING")
    valid_until = models.DateField()
    # Rendering, issuance and download are deliberately deferred to the card phase.


class FacilitatorStatusHistory(models.Model):
    facilitator = models.ForeignKey(
        Facilitator, on_delete=models.PROTECT, related_name="status_history"
    )
    appointment = models.ForeignKey(FacilitatorAppointment, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    reason = models.TextField(max_length=2000)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(default=dict)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["pk"]
        default_permissions = ("view",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Status history cannot be modified.")
        kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Status history cannot be deleted.")
