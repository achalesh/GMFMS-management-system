from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import RequestBudget


class Command(BaseCommand):
    help = "Remove expired password-reset rate-limit buckets (does not delete audit records)."

    def handle(self, *args, **options):
        count, _ = RequestBudget.objects.filter(
            expires_at__lt=timezone.now() - timedelta(days=1)
        ).delete()
        self.stdout.write(f"Removed {count} expired rate-limit buckets.")
