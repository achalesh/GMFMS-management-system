import hashlib
import json

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Load the source-checked, bundled 14-district / 152-block / 941-Panchayat snapshot."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--update", action="store_true")

    def handle(self, *args, **options):
        folder = settings.BASE_DIR / "data" / "kerala"
        source = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
        csv_file = folder / "locations.csv"
        if hashlib.sha256(csv_file.read_bytes()).hexdigest() != source["csv_sha256"]:
            raise CommandError(
                "Bundled dataset checksum mismatch; inspect source provenance before seeding."
            )
        call_command(
            "import_locations",
            str(csv_file),
            source="Kerala SEC + LSGD directories, retrieved 2026-09-28; hierarchy cross-checked with LSGD 2015 reference.",
            dry_run=options["dry_run"],
            update=options["update"],
            stdout=self.stdout,
        )
        if not options["dry_run"]:
            call_command("resolve_location_jurisdictions", stdout=self.stdout)
