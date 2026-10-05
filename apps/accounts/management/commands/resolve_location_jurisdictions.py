from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import UserJurisdiction
from apps.audit.services import record_event
from apps.locations.models import Block, District


class Command(BaseCommand):
    help = "Resolve legacy jurisdiction codes to exact authoritative location foreign keys; unmatched scopes remain denied."

    @transaction.atomic
    def handle(self, *args, **options):
        resolved = unresolved = 0
        for scope in UserJurisdiction.objects.select_for_update().exclude(scope="STATE"):
            district = District.objects.filter(district_code=scope.district_code).first()
            block = (
                Block.objects.filter(block_code=scope.block_code, district=district).first()
                if scope.scope == "BLOCK"
                else None
            )
            if district and (scope.scope == "DISTRICT" or block):
                if scope.district_id != district.pk or scope.block_id != (
                    block.pk if block else None
                ):
                    scope.district = district
                    scope.block = block
                    try:
                        scope.full_clean()
                    except ValidationError:
                        unresolved += 1
                        continue
                    scope.save(update_fields=["district", "block", "updated_at"])
                    record_event(
                        actor=None,
                        action="permissions.scope_resolved",
                        entity=scope,
                        new_values={
                            "district": district.district_code,
                            "block": block.block_code if block else "",
                        },
                    )
                    resolved += 1
            else:
                unresolved += 1
        self.stdout.write(
            f"Resolved {resolved} legacy scopes; {unresolved} unmatched scopes remain denied."
        )
