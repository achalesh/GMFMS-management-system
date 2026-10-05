# ruff: noqa: E402
"""Seed review-only browser fixtures in the isolated QA database."""

import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'artifacts/ui.sqlite3').as_posix()}"
os.environ["MEDIA_ROOT"] = "artifacts/ui-media"
import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.locations.models import GramaPanchayat
from apps.registrations.catalog import CONSENT
from apps.registrations.models import Application, Language, RegistrationUpload
from apps.registrations.uploads import validate_upload

panchayats = list(
    GramaPanchayat.objects.filter(active=True).exclude(appointments__status="ACTIVE")[:3]
)
fixtures = {}
for index, kind in enumerate(["approve", "correct", "reject"]):
    name = f"Browser QA {kind.title()}"
    app = Application.objects.create(
        application_number="GMF-QA-" + uuid.uuid4().hex[:12],
        panchayat=panchayats[index],
        full_name=name,
        normalized_name=name.lower(),
        mobile=f"98765432{index:02}",
        whatsapp=f"98765432{index:02}",
        address="Isolated QA address",
        pin_code="695001",
        consent_version="1.0",
        consent_text=CONSENT,
        consented_at=timezone.now(),
    )
    app.languages.add(Language.objects.get(code="malayalam"))
    for slot, filename, mime in [
        ("photo", "registration-test-photo.png", "image/png"),
        ("doc_certificate", "registration-test.pdf", "application/pdf"),
    ]:
        data = validate_upload(
            SimpleUploadedFile(
                filename, (ROOT / "artifacts" / filename).read_bytes(), content_type=mime
            ),
            max_bytes=5 * 1024 * 1024,
            photo=slot == "photo",
        )
        RegistrationUpload.objects.create(
            application=app,
            slot=slot,
            file=data["content"],
            content_type=data["content_type"],
            byte_size=data["byte_size"],
            sha256=data["sha256"],
        )
    fixtures[kind] = {"id": str(app.pk), "number": app.application_number, "name": name}
(ROOT / "artifacts/review-fixtures.json").write_text(json.dumps(fixtures), encoding="utf-8")
print("Three review workflow fixtures prepared in the isolated QA database.")
