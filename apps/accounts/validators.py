from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class RepeatedPatternValidator:
    def validate(self, password, user=None):
        for length in range(1, len(password) // 2 + 1):
            if len(password) % length == 0 and password == password[:length] * (
                len(password) // length
            ):
                raise ValidationError(
                    _("Your password must not consist entirely of a repeated pattern."),
                    code="password_repeated_pattern",
                )

    def get_help_text(self):
        return _("Your password must not consist entirely of a repeated pattern.")
