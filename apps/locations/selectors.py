from django.db.models import Q

from apps.accounts.policies import scopes_for

from .models import Block, District, GramaPanchayat


def active_districts():
    return District.objects.filter(active=True, state__active=True)


def active_blocks():
    return Block.objects.filter(active=True, district__active=True, district__state__active=True)


def active_panchayats():
    return GramaPanchayat.objects.filter(
        active=True,
        block__active=True,
        block__district__active=True,
        block__district__state__active=True,
    )


def staff_locations(user, model):
    queryset = model.objects.all()
    if not user.is_authenticated or not user.is_active:
        return queryset.none()
    if user.is_superuser:
        return queryset
    condition = Q(pk__in=[])
    for scope in scopes_for(user, "locations.view"):
        if scope.scope == "STATE":
            return queryset
        if model is District:
            condition |= Q(pk=scope.district_id)
        elif model is Block:
            condition |= (
                Q(pk=scope.block_id) if scope.scope == "BLOCK" else Q(district_id=scope.district_id)
            )
        elif model is GramaPanchayat:
            condition |= (
                Q(block_id=scope.block_id)
                if scope.scope == "BLOCK"
                else Q(block__district_id=scope.district_id)
            )
    return queryset.filter(condition).distinct()
