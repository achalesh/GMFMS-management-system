from django.db.models import Case, CharField, F, Q, Value, When
from django.utils import timezone

from apps.accounts.policies import can, scope_queryset, scopes_for
from apps.locations.models import GramaPanchayat

from .models import Facilitator, FacilitatorAppointment


def can_enter(user):
    return bool(
        user.is_authenticated
        and user.is_active
        and (user.is_superuser or scopes_for(user, "facilitators.view"))
    )


def locations_for(user, capability="facilitators.view"):
    return scope_queryset(
        user,
        GramaPanchayat.objects.select_related("block__district__state"),
        capability,
        district_field="block__district__district_code",
        block_field="block__block_code",
    )


def permitted(user, panchayat, capability="facilitators.change"):
    return can(
        user,
        capability,
        district_code=panchayat.block.district.district_code,
        block_code=panchayat.block.block_code,
    )


def registry_for(user, capability="facilitators.view"):
    return scope_queryset(
        user,
        Facilitator.objects.select_related(
            "current_appointment__panchayat__block__district", "application"
        ),
        capability,
        district_field="current_appointment__panchayat__block__district__district_code",
        block_field="current_appointment__panchayat__block__block_code",
    ).annotate(
        display_status=Case(
            When(status="ACTIVE", valid_until__lt=timezone.localdate(), then=Value("EXPIRED")),
            default=F("status"),
            output_field=CharField(),
        )
    )


def active_appointments():
    today = timezone.localdate()
    return FacilitatorAppointment.objects.filter(
        ended_at__isnull=True,
        status="ACTIVE",
        facilitator__status="ACTIVE",
        facilitator__valid_until__gte=today,
        effective_from__lte=today,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))


def primary_appointments():
    return active_appointments().filter(role="PRIMARY")
