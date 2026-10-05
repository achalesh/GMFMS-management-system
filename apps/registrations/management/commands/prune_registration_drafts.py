from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.registrations.models import RegistrationDraft


class Command(BaseCommand):
    help = "Delete expired registration drafts and their private draft uploads; preserve submitted applications."

    def handle(self, *args, **options):
        count = 0
        for pk in (
            RegistrationDraft.objects.filter(expires_at__lte=timezone.now())
            .values_list("pk", flat=True)
            .iterator()
        ):
            with transaction.atomic():
                draft = (
                    RegistrationDraft.objects.select_for_update()
                    .filter(pk=pk, expires_at__lte=timezone.now())
                    .first()
                )
                if not draft:
                    continue
                for upload in draft.uploads.all():
                    transaction.on_commit(
                        lambda s=upload.file.storage, n=upload.file.name: s.delete(n)
                    )
                draft.delete()
                count += 1
        self.stdout.write(f"Removed {count} expired drafts. Submitted applications retained.")
