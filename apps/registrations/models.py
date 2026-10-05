import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.audit.models import AppendOnlyQuerySet
from apps.common.models import TimestampedModel


def draft_expiry():
    return timezone.now() + timedelta(hours=24)


class ChoiceMaster(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Skill(ChoiceMaster):
    pass


class Equipment(ChoiceMaster):
    pass


class Language(ChoiceMaster):
    pass


class DocumentType(ChoiceMaster):
    required = models.BooleanField(default=False)
    instructions = models.CharField(max_length=300, blank=True)


class RegistrationDraft(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data = models.JSONField(default=dict)
    completed_step = models.PositiveSmallIntegerField(default=0)
    revision = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField(default=draft_expiry, db_index=True)


class ApplicationSequence(models.Model):
    year = models.PositiveSmallIntegerField(primary_key=True)
    value = models.PositiveIntegerField(default=0)


class Application(TimestampedModel):
    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Submitted"
        UNDER_REVIEW = "UNDER_REVIEW", "Under review"
        CORRECTION_REQUIRED = "CORRECTION_REQUIRED", "Correction required"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.OneToOneField(
        RegistrationDraft,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="application",
    )
    application_number = models.CharField(max_length=30, unique=True)
    revision = models.PositiveIntegerField(default=1)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reviewed_applications",
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="decided_applications",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=24, choices=Status.choices, default=Status.SUBMITTED, db_index=True
    )
    panchayat = models.ForeignKey(
        "locations.GramaPanchayat", on_delete=models.PROTECT, related_name="applications"
    )
    full_name = models.CharField(max_length=150)
    normalized_name = models.CharField(max_length=180, db_index=True, default="")
    name_ml = models.CharField(max_length=180, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    mobile = models.CharField(max_length=10, db_index=True)
    whatsapp = models.CharField(max_length=10, blank=True)
    email = models.EmailField(blank=True, db_index=True)
    address = models.TextField(max_length=1500)
    pin_code = models.CharField(max_length=6)
    occupation = models.CharField(max_length=150, blank=True)
    qualification = models.CharField(max_length=180, blank=True)
    current_organization = models.CharField(max_length=180, blank=True)
    designation = models.CharField(max_length=150, blank=True)
    media_experience = models.TextField(max_length=2000, blank=True)
    years_experience = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(80)]
    )
    skills = models.ManyToManyField(Skill, blank=True)
    equipment = models.ManyToManyField(Equipment, blank=True)
    languages = models.ManyToManyField(Language, blank=True)
    other_skill = models.CharField(max_length=200, blank=True)
    other_equipment = models.CharField(max_length=200, blank=True)
    other_language = models.CharField(max_length=100, blank=True)
    social_profiles = models.JSONField(default=dict, blank=True)
    emergency_name = models.CharField(max_length=150, blank=True)
    emergency_relationship = models.CharField(max_length=80, blank=True)
    emergency_mobile = models.CharField(max_length=10, blank=True)
    consent_version = models.CharField(max_length=30)
    consent_text = models.JSONField(default=dict)
    consented_at = models.DateTimeField()
    public_mobile_consent = models.BooleanField(default=False)
    public_email_consent = models.BooleanField(default=False)
    public_social_consent = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)

    def __str__(self):
        return self.application_number

    class Meta:
        ordering = ["-submitted_at"]


class RegistrationUpload(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        RegistrationDraft, null=True, on_delete=models.CASCADE, related_name="uploads"
    )
    application = models.ForeignKey(
        Application, null=True, on_delete=models.PROTECT, related_name="uploads"
    )
    slot = models.CharField(max_length=60)
    file = models.FileField(upload_to="registrations/%Y/%m", max_length=250)
    content_type = models.CharField(max_length=40)
    byte_size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)

    @property
    def display_name(self):
        if self.slot == "photo":
            return "Profile photograph"
        kind = DocumentType.objects.filter(code=self.slot.removeprefix("doc_")).first()
        return kind.name if kind else "Supporting document"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "slot"], name="unique_registration_draft_upload"
            ),
            models.UniqueConstraint(
                fields=["application", "slot"], name="unique_registration_application_upload"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(draft__isnull=False, application__isnull=True)
                    | models.Q(draft__isnull=True, application__isnull=False)
                ),
                name="registration_upload_one_owner",
            ),
        ]


class DuplicateWarning(TimestampedModel):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="duplicate_warnings"
    )
    other_application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="+")
    reasons = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["application", "other_application"],
                name="unique_application_duplicate_warning",
            )
        ]


class ReviewEvent(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="review_events"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    from_status = models.CharField(max_length=24)
    to_status = models.CharField(max_length=24)
    reason = models.TextField(blank=True, max_length=2000)
    changes = models.JSONField(default=dict, blank=True)
    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "pk"]
        default_permissions = ("view",)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Review history cannot be modified.")
        kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Review history cannot be deleted.")


class CorrectionRequest(TimestampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="correction_requests"
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    token_hash = models.CharField(max_length=64, unique=True)
    allowed_fields = models.JSONField(default=list)
    message = models.TextField(max_length=2000)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
