from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Accounts & access"

    def ready(self):
        from . import checks, signals  # noqa: F401
