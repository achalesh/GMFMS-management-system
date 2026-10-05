import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def card_token():
    return secrets.token_urlsafe(32)


def artifact_path(instance, filename):
    return f"idcards/{uuid.uuid4().hex}/{filename}"


class IdentityCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facilitator = models.ForeignKey(
        "facilitators.Facilitator", on_delete=models.PROTECT, related_name="cards"
    )
    appointment = models.ForeignKey("facilitators.FacilitatorAppointment", on_delete=models.PROTECT)
    card_number = models.CharField(max_length=80, unique=True)
    version = models.PositiveIntegerField()
    public_token = models.CharField(max_length=64, unique=True, default=card_token, editable=False)
    status = models.CharField(
        max_length=20,
        default="ISSUED",
        choices=[("ISSUED", "Issued"), ("REVOKED", "Revoked"), ("SUPERSEDED", "Superseded")],
    )
    issue_date = models.DateField(default=timezone.localdate)
    valid_until = models.DateField()
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="generated_cards"
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revoked_cards",
    )
    revocation_reason = models.TextField(max_length=2000, blank=True)
    source_digest = models.CharField(max_length=64)
    snapshot = models.JSONField(default=dict)
    pdf = models.FileField(upload_to=artifact_path)
    print_pdf = models.FileField(upload_to=artifact_path)
    front = models.FileField(upload_to=artifact_path)
    back = models.FileField(upload_to=artifact_path)
    pdf_sha256 = models.CharField(max_length=64)
    print_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ["-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["facilitator", "version"], name="unique_facilitator_card_version"
            )
        ]
        default_permissions = ("view",)
