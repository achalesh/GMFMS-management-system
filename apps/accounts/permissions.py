from rest_framework.permissions import BasePermission

from .policies import can


class HasDashboardAccess(BasePermission):
    def has_permission(self, request, view):
        return can(request.user, "dashboard.view")
