from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from apps.common.models import TimestampedModel


class SingletonSettings(TimestampedModel):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    revision = models.PositiveIntegerField(default=1, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)


class OrganizationSetting(SingletonSettings):
    application_name = models.CharField(
        max_length=160, default="Gramaswaraj Media Facilitator Management System"
    )
    short_name = models.CharField(max_length=30, default="Gramaswaraj")
    name = models.CharField(max_length=180, default="Kerala Grama Panchayat Association")
    name_ml = models.CharField(max_length=200, default="ഗ്രാമസ്വരാജ് മീഡിയ ഫെസിലിറ്റേറ്റർ മാനേജ്മെന്റ് സിസ്റ്റം")
    network_name = models.CharField(max_length=180, default="Digital Media & Broadcasting Network")
    address = models.TextField(blank=True, max_length=1500)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    signatory_name = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="one_organization_setting")
        ]

    def __str__(self):
        return self.name


class SystemSetting(SingletonSettings):
    facilitator_id_prefix = models.CharField(
        max_length=12, default="GS-MF", validators=[RegexValidator(r"^[A-Z][A-Z0-9-]*$")]
    )
    default_validity_days = models.PositiveIntegerField(
        default=365, validators=[MinValueValidator(1), MaxValueValidator(3650)]
    )
    one_primary_per_panchayat = models.BooleanField(default=True)
    public_directory_enabled = models.BooleanField(default=False)
    allow_public_mobile = models.BooleanField(default=False)
    allow_public_email = models.BooleanField(default=False)
    allow_public_social_profiles = models.BooleanField(default=False)
    max_upload_mb = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    consent_version = models.CharField(max_length=30, default="1.0")

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="one_system_setting")]

    def __str__(self):
        return "System policy"
