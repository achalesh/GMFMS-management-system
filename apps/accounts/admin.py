from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name", "email")}),
        ("Security", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Preferences", {"fields": ("preferred_language",)}),
    )
    filter_horizontal = ()
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "password1", "password2")}),
    )
    # Role assignments are edited through validated services/commands, never inline.
    list_display = ("username", "email", "is_active", "is_superuser")

    def has_module_permission(self, request):
        from .policies import can

        return can(request.user, "accounts.manage")

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False  # Deactivate accounts to preserve attribution.

    def save_model(self, request, obj, form, change):
        from apps.audit.services import record_event

        fields = ("is_active", "is_staff", "is_superuser")
        old = User.objects.get(pk=obj.pk) if change else None
        old_values = {key: getattr(old, key) for key in fields} if old else {}
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            action="account.updated" if change else "account.created",
            entity=obj,
            old_values=old_values,
            new_values={key: getattr(obj, key) for key in fields},
        )

    def user_change_password(self, request, id, form_url=""):
        from apps.audit.services import record_event

        response = super().user_change_password(request, id, form_url)
        if request.method == "POST" and response.status_code == 302:
            record_event(
                actor=request.user,
                action="auth.password_changed_by_admin",
                entity=self.get_object(request, id),
            )
        return response
