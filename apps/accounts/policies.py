from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Role, UserJurisdiction

# Capability names are stable contracts for subsequent phases.
CAPABILITIES = {
    Role.Code.SUPER_ADMIN: frozenset(
        {
            "dashboard.view",
            "organization.change",
            "system.change",
            "accounts.manage",
            "audit.view",
            "applications.view",
            "applications.review",
            "applications.approve",
            "facilitators.view",
            "facilitators.change",
            "contacts.view",
            "cards.issue",
            "reports.export",
        }
    ),
    Role.Code.STATE_ADMIN: frozenset(
        {
            "dashboard.view",
            "organization.change",
            "audit.view",
            "applications.view",
            "applications.review",
            "applications.approve",
            "facilitators.view",
            "facilitators.change",
            "contacts.view",
            "cards.issue",
            "reports.export",
        }
    ),
    Role.Code.DISTRICT_ADMIN: frozenset(
        {
            "dashboard.view",
            "applications.view",
            "applications.review",
            "applications.approve",
            "facilitators.view",
            "facilitators.change",
            "contacts.view",
            "cards.issue",
            "reports.export",
        }
    ),
    Role.Code.BLOCK_COORDINATOR: frozenset(
        {
            "dashboard.view",
            "applications.view",
            "applications.review",
            "facilitators.view",
            "contacts.view",
        }
    ),
    Role.Code.REVIEWER: frozenset(
        {
            "dashboard.view",
            "applications.view",
            "applications.review",
            "facilitators.view",
            "contacts.view",
        }
    ),
    Role.Code.ID_CARD_OPERATOR: frozenset({"dashboard.view", "facilitators.view", "cards.issue"}),
    Role.Code.VIEWER: frozenset({"dashboard.view", "facilitators.view"}),
}
for code in CAPABILITIES:
    CAPABILITIES[code] = CAPABILITIES[code] | {"locations.view"}
CAPABILITIES[Role.Code.SUPER_ADMIN] = CAPABILITIES[Role.Code.SUPER_ADMIN] | {"locations.manage"}

GLOBAL_ONLY = {
    "organization.change",
    "system.change",
    "accounts.manage",
    "audit.view",
    "locations.manage",
}


def scopes_for(user, capability):
    if not user or not user.is_authenticated or not user.is_active:
        return []
    scopes = UserJurisdiction.objects.filter(
        assignment__user=user, assignment__active=True
    ).select_related("assignment__role", "district__state", "block")
    valid = []
    for scope in scopes:
        role = scope.assignment.role.code
        if scope.scope == "STATE":
            if scope.district_id or scope.block_id or scope.district_code or scope.block_code:
                continue
        else:
            if (
                not scope.district_id
                or not scope.district.active
                or not scope.district.state.active
                or scope.district.district_code != scope.district_code
            ):
                continue
            if scope.scope == "DISTRICT" and (scope.block_id or scope.block_code):
                continue
            if scope.scope == "BLOCK" and (
                not scope.block_id
                or not scope.block.active
                or scope.block.district_id != scope.district_id
                or scope.block.block_code != scope.block_code
            ):
                continue

        # Also enforce role/scope compatibility at read time: fail closed for
        # malformed rows inserted outside the service's model validation.
        if role == Role.Code.DISTRICT_ADMIN and scope.scope != "DISTRICT":
            continue
        if role == Role.Code.BLOCK_COORDINATOR and scope.scope != "BLOCK":
            continue
        if role in {Role.Code.SUPER_ADMIN, Role.Code.STATE_ADMIN} and scope.scope != "STATE":
            continue
        if capability in CAPABILITIES.get(role, ()):
            valid.append(scope)
    return valid


def can(user, capability, *, district_code=None, block_code=None):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if capability not in set().union(*CAPABILITIES.values()):
        return False
    if user.is_superuser:
        return True
    for scope in scopes_for(user, capability):
        if scope.scope == "STATE":
            return True
        if capability in GLOBAL_ONLY:
            continue
        if district_code is None:
            # Scope-less checks only authorize entering the dashboard. Data access
            # MUST supply an object scope or use scope_queryset().
            if capability in {"dashboard.view", "locations.view"}:
                return True
            continue
        if scope.district_code != district_code:
            continue
        if scope.scope == "DISTRICT" or (scope.scope == "BLOCK" and block_code == scope.block_code):
            return True
    return False


def scope_queryset(
    user, queryset, capability, *, district_field="district_code", block_field="block_code"
):
    if not user or not user.is_authenticated or not user.is_active:
        return queryset.none()
    if capability not in set().union(*CAPABILITIES.values()):
        return queryset.none()
    if user.is_superuser:
        return queryset
    predicate = Q(pk__in=[])
    for scope in scopes_for(user, capability):
        if scope.scope == "STATE":
            return queryset
        if capability in GLOBAL_ONLY:
            continue
        condition = Q(**{district_field: scope.district_code})
        if scope.scope == "BLOCK":
            condition &= Q(**{block_field: scope.block_code})
        predicate |= condition
    return queryset.filter(predicate).distinct()


def require_capability(capability):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not can(request.user, capability):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
