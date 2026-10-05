from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from apps.accounts.models import User
from apps.locations.importing import import_locations, parse_file


class Command(BaseCommand):
    help = "Atomically import a UTF-8 CSV or XLSX location master. Shell access is a trusted maintenance boundary."

    def add_arguments(self, parser):
        parser.add_argument("file", type=Path)
        parser.add_argument("--source", required=True)
        parser.add_argument(
            "--actor",
            help="Optional named administrator for attribution; omitted means system maintenance.",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--update",
            action="store_true",
            help="Allow descriptive updates, never reparenting or deleting.",
        )

    def handle(self, *args, **options):
        try:
            actor = User.objects.get(username=options["actor"]) if options["actor"] else None
            with options["file"].open("rb") as upload:
                rows, digest = parse_file(upload)
            summary = import_locations(
                rows=rows,
                sha256=digest,
                source=options["source"],
                actor=actor,
                system=actor is None,
                dry_run=options["dry_run"],
                update_existing=options["update"],
            )
        except (
            ValidationError,
            PermissionDenied,
            IntegrityError,
            OSError,
            User.DoesNotExist,
        ) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                ("DRY RUN: no changes saved. " if options["dry_run"] else "Imported. ")
                + str({key: value for key, value in summary.items() if key != "changes"})
            )
        )
