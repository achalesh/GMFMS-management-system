from django.contrib import admin
from django.contrib.auth.models import Group

from apps.accounts.models import Role
from apps.accounts.policies import scopes_for


def has_emergency_admin_permission(request):
    user = request.user
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return False
    return user.is_superuser or any(
        scope.assignment.role.code == Role.Code.SUPER_ADMIN
        for scope in scopes_for(user, "accounts.manage")
    )


admin.site.has_permission = has_emergency_admin_permission
admin.site.site_header = "Gramaswaraj · Emergency administration"
admin.site.site_title = "GMFMS administration"
admin.site.index_title = "System maintenance"

# Django groups do not define application capabilities; avoid a second permissions UI.

admin.site.unregister(Group)
