from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.registrations.catalog import DOCUMENTS, EQUIPMENT, LANGUAGES, SKILLS
from apps.registrations.models import DocumentType, Equipment, Language, Skill


def seed():
    for model, labels in [(Skill, SKILLS), (Equipment, EQUIPMENT), (Language, LANGUAGES)]:
        for index, label in enumerate(labels):
            model.objects.get_or_create(
                code=slugify(label), defaults={"name": label, "display_order": index}
            )
    for index, (code, label) in enumerate(DOCUMENTS):
        DocumentType.objects.get_or_create(
            code=code, defaults={"name": label, "display_order": index}
        )


class Command(BaseCommand):
    help = "Seed missing registration skills, equipment, languages and document types without overwriting configuration."

    def handle(self, *args, **options):
        seed()
        self.stdout.write("Registration choices seeded.")
