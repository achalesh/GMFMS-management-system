import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.common.models import TimestampedModel

code_validator = RegexValidator(
    r"^[A-Z0-9_-]+$", "Use uppercase letters, digits, underscores or hyphens."
)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    preferred_language = models.CharField(
        max_length=2, choices=[("en", "English"), ("ml", "മലയാളം")], default="en"
    )

    REQUIRED_FIELDS = ["email"]

    def clean(self):
        self.email = self.email.strip().lower()
        super().clean()

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.username


class Role(models.Model):
    class Code(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super administrator"
        STATE_ADMIN = "STATE_ADMIN", "State administrator"
        DISTRICT_ADMIN = "DISTRICT_ADMIN", "District administrator"
        BLOCK_COORDINATOR = "BLOCK_COORDINATOR", "Block coordinator"
        REVIEWER = "REVIEWER", "Reviewer"
        ID_CARD_OPERATOR = "ID_CARD_OPERATOR", "ID card operator"
        VIEWER = "VIEWER", "Viewer"

    code = models.CharField(max_length=24, choices=Code.choices, unique=True)
    description = models.CharField(max_length=250)

    def __str__(self):
        return self.get_code_display()


class UserRole(TimestampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.PROTECT)
    granted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "role"], name="unique_user_role")]

    def __str__(self):
        return f"{self.user} / {self.role}"


class UserJurisdiction(TimestampedModel):
    """Role-scoped authoritative FKs; original codes retained for legacy reconciliation."""

    class Scope(models.TextChoices):
        STATE = "STATE", "Kerala (state-wide)"
        DISTRICT = "DISTRICT", "District"
        BLOCK = "BLOCK", "Block"

    assignment = models.ForeignKey(UserRole, on_delete=models.CASCADE, related_name="jurisdictions")
    scope = models.CharField(max_length=10, choices=Scope.choices)
    district_code = models.CharField(max_length=20, blank=True, validators=[code_validator])
    block_code = models.CharField(max_length=30, blank=True, validators=[code_validator])

    district = models.ForeignKey(
        "locations.District",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="jurisdictions",
    )
    block = models.ForeignKey(
        "locations.Block",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="jurisdictions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "scope", "district_code", "block_code"],
                name="unique_role_jurisdiction",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(scope="STATE", district_code="", block_code="")
                    | (models.Q(scope="DISTRICT", block_code="") & ~models.Q(district_code=""))
                    | (
                        models.Q(scope="BLOCK")
                        & ~models.Q(district_code="")
                        & ~models.Q(block_code="")
                    )
                ),
                name="valid_jurisdiction_shape",
            ),
        ]

    def clean(self):
        super().clean()
        role = self.assignment.role.code
        if self.scope == "STATE" and (self.district_id or self.block_id):
            raise ValidationError("State scope cannot contain geographic references.")
        if self.scope != "STATE":
            if not self.district_id or self.district.district_code != self.district_code:
                raise ValidationError("An exact location-master district reference is required.")
            if not self.district.active or not self.district.state.active:
                raise ValidationError("The jurisdiction district must be active.")
            if self.scope == "DISTRICT" and self.block_id:
                raise ValidationError("District scope cannot contain a block reference.")
            if self.scope == "BLOCK" and (
                not self.block_id
                or self.block.block_code != self.block_code
                or self.block.district_id != self.district_id
                or not self.block.active
            ):
                raise ValidationError(
                    "An active block belonging to the assigned district is required."
                )

        if self.scope == self.Scope.STATE and (self.district_code or self.block_code):
            raise ValidationError("State scope must not contain district or block codes.")
        if self.scope == self.Scope.DISTRICT and (not self.district_code or self.block_code):
            raise ValidationError("District scope requires only a district code.")
        if self.scope == self.Scope.BLOCK and (not self.district_code or not self.block_code):
            raise ValidationError("Block scope requires both district and block codes.")
        if role == Role.Code.DISTRICT_ADMIN and self.scope != self.Scope.DISTRICT:
            raise ValidationError("District administrators require district scope.")
        if role == Role.Code.BLOCK_COORDINATOR and self.scope != self.Scope.BLOCK:
            raise ValidationError("Block coordinators require block scope.")
        if (
            role in {Role.Code.SUPER_ADMIN, Role.Code.STATE_ADMIN}
            and self.scope != self.Scope.STATE
        ):
            raise ValidationError("State and super administrators require state scope.")


class RequestBudget(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    hits = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(db_index=True)
