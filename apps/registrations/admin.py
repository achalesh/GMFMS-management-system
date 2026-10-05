from django.contrib import admin

from apps.accounts.policies import can

from .models import Application, DuplicateWarning


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_view_permission(self, request, obj=None):
        return can(request.user, "accounts.manage")

    def has_module_permission(self, request):
        return can(request.user, "accounts.manage")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WarningInline(admin.TabularInline):
    model = DuplicateWarning
    fk_name = "application"
    fields = ["other_application", "reasons", "created_at"]
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return can(request.user, "accounts.manage")


@admin.register(Application)
class ApplicationAdmin(ReadOnlyAdmin):
    list_display = [
        "application_number",
        "full_name",
        "panchayat",
        "status",
        "submitted_at",
        "warning_count",
    ]
    list_filter = ["status", "panchayat__block__district"]
    search_fields = ["application_number", "full_name"]
    readonly_fields = [field.name for field in Application._meta.fields] + [
        "skills",
        "languages",
        "equipment",
    ]
    inlines = [WarningInline]
    list_select_related = ["panchayat"]

    def get_queryset(self, request):
        from django.db.models import Count

        return super().get_queryset(request).annotate(warnings_count=Count("duplicate_warnings"))

    @admin.display(description="Duplicate warnings")
    def warning_count(self, obj):
        return obj.warnings_count
