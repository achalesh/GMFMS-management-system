from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm

from .models import User


class StaffAuthenticationForm(AuthenticationForm):
    username = AuthenticationForm.base_fields["username"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class SafePasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        # Always use exact case-insensitive email matching, never username matching.
        return (
            u
            for u in User.objects.filter(email__iexact=email, is_active=True)
            if u.has_usable_password()
        )
