from apps.accounts.policies import can
from apps.facilitators.selectors import can_enter as registry_access
from apps.registrations.review_selectors import can_enter

from .models import OrganizationSetting


def branding(request):
    return {
        "organization": OrganizationSetting.objects.filter(pk=1).first(),
        "access": {
            "organization": can(request.user, "organization.change"),
            "system": can(request.user, "system.change"),
            "accounts": can(request.user, "accounts.manage"),
            "audit": can(request.user, "audit.view"),
            "locations": can(request.user, "locations.view"),
            "applications": can_enter(request.user),
            "facilitators": registry_access(request.user),
        },
    }
