from django.core.management.base import BaseCommand

from apps.facilitators.services import expire_identities


class Command(BaseCommand):
    help = "Record expired active facilitator identities and their status history."

    def handle(self, *args, **options):
        count = expire_identities()
        self.stdout.write(f"Recorded expiry for {count} facilitator identities.")
