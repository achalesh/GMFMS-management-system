from apps.accounts.policies import can, scope_queryset, scopes_for

from .models import Application


def can_enter(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or scopes_for(user, "applications.view"))
    )


def applications_for(user, capability="applications.view"):
    return scope_queryset(
        user,
        Application.objects.all(),
        capability,
        district_field="panchayat__block__district__district_code",
        block_field="panchayat__block__block_code",
    )


def can_act(user, application, capability):
    return can(
        user,
        capability,
        district_code=application.panchayat.block.district.district_code,
        block_code=application.panchayat.block.block_code,
    )
