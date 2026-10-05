from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.common.models import TimestampedModel

code_validator = RegexValidator(
    r"^[A-Z0-9_-]+$", "Use uppercase letters, numbers, underscores or hyphens."
)


class Location(TimestampedModel):
    name_en = models.CharField(max_length=150)
    name_ml = models.CharField(max_length=180, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    revision = models.PositiveIntegerField(default=1)
    identity_fields = ()

    class Meta:
        abstract = True
        ordering = ["name_en"]

    def __str__(self):
        return self.name_en

    def clean(self):
        super().clean()
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(*self.identity_fields).first()
            if previous and any(
                previous[field] != getattr(self, field) for field in self.identity_fields
            ):
                raise ValidationError(
                    "Codes and parent relationships are immutable. Archive the record and use a separately reviewed migration for boundary changes."
                )


class State(Location):
    code = models.CharField(max_length=10, unique=True, validators=[code_validator])
    identity_fields = ("code",)


class District(Location):
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="districts")
    district_code = models.CharField(max_length=20, unique=True, validators=[code_validator])
    display_order = models.PositiveSmallIntegerField(default=0)
    identity_fields = ("district_code", "state_id")

    class Meta(Location.Meta):
        ordering = ["display_order", "name_en"]


class Block(Location):
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="blocks")
    block_code = models.CharField(max_length=30, unique=True, validators=[code_validator])
    lsg_code = models.CharField(max_length=20, blank=True, validators=[code_validator])
    identity_fields = ("block_code", "district_id")


class GramaPanchayat(Location):
    # District is normalized through block: contradictory district/block pairs
    # cannot be stored. It remains available as district and district_id properties.
    block = models.ForeignKey(Block, on_delete=models.PROTECT, related_name="panchayats")
    sec_local_body_code = models.CharField(max_length=30, unique=True, validators=[code_validator])
    lsg_code = models.CharField(max_length=20, blank=True, validators=[code_validator])
    official_email = models.EmailField(blank=True)
    office_phone = models.CharField(max_length=30, blank=True)
    identity_fields = ("sec_local_body_code", "block_id")

    @property
    def district(self):
        return self.block.district

    @property
    def district_id(self):
        return self.block.district_id


class LocationImport(TimestampedModel):
    source = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64, db_index=True)
    imported_by = models.ForeignKey("accounts.User", null=True, on_delete=models.PROTECT)
    summary = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
        default_permissions = ("view",)
