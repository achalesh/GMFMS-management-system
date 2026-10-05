from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the first administrator using Django's interactive password validation."

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            raise CommandError(
                "An initial administrator already exists. Use createsuperuser for another."
            )
        call_command("createsuperuser", interactive=True)
