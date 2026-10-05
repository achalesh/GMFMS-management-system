from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.policies import can
from apps.audit.services import record_event
from apps.registrations.models import DocumentType


class Command(BaseCommand):
    help = "Configure a registration document requirement with an audited administrator identity."

    def add_arguments(self, parser):
        parser.add_argument("code")
        parser.add_argument("--actor", required=True)
        parser.add_argument("--required", choices=["yes", "no"])
        parser.add_argument("--active", choices=["yes", "no"])
        parser.add_argument("--instructions")
        parser.add_argument("--reason", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        actor = User.objects.filter(username=options["actor"]).first()
        if not can(actor, "system.change") or not options["reason"].strip():
            raise CommandError("An authorized administrator and reason are required.")
        obj = DocumentType.objects.select_for_update().filter(code=options["code"]).first()
        if not obj:
            raise CommandError("Unknown document code.")
        old = {"required": obj.required, "active": obj.active, "instructions": obj.instructions}
        for key in ["required", "active"]:
            if options[key] is not None:
                setattr(obj, key, options[key] == "yes")
        if options["instructions"] is not None:
            obj.instructions = options["instructions"]
        obj.full_clean()
        obj.save()
        record_event(
            actor=actor,
            action="registration.document_policy_changed",
            entity=obj,
            old_values=old,
            new_values={
                "required": obj.required,
                "active": obj.active,
                "instructions": obj.instructions,
            },
            reason=options["reason"],
        )
        self.stdout.write("Document policy updated.")
