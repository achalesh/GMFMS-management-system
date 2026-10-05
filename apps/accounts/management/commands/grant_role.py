from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, User, UserJurisdiction
from apps.accounts.services import grant_role


class Command(BaseCommand):
    help = "Assign a validated role and jurisdiction; requires an authorized actor."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role", choices=Role.Code.values)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--scope", choices=UserJurisdiction.Scope.values, required=True)
        parser.add_argument("--district", default="")
        parser.add_argument("--block", default="")

    def handle(self, *args, **options):
        try:
            actor = User.objects.get(username=options["actor"], is_active=True)
            user = User.objects.get(username=options["username"])
            grant_role(
                actor=actor,
                user=user,
                role_code=options["role"],
                scope=options["scope"],
                district_code=options["district"],
                block_code=options["block"],
            )
        except (User.DoesNotExist, ValidationError, PermissionDenied) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Role and jurisdiction saved; audit event recorded."))
