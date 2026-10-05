from django.core.exceptions import PermissionDenied
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, User, UserRole
from apps.accounts.services import revoke_role


class Command(BaseCommand):
    help = "Deactivate an entire role assignment and retain its history."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("role", choices=Role.Code.values)
        parser.add_argument("--actor", required=True)
        parser.add_argument("--reason", required=True)

    def handle(self, *args, **options):
        try:
            actor = User.objects.get(username=options["actor"], is_active=True)
            assignment = UserRole.objects.get(
                user__username=options["username"], role__code=options["role"]
            )
            revoke_role(actor=actor, assignment=assignment, reason=options["reason"])
        except (User.DoesNotExist, UserRole.DoesNotExist, PermissionDenied, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS("Role deactivated; audit event recorded."))
