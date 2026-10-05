# ruff: noqa: E402
"""Synthetic registry fixtures, exclusively in the isolated browser QA database."""

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
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.facilitators.selectors import primary_appointments
from apps.locations.models import GramaPanchayat
from apps.registrations.catalog import CONSENT
from apps.registrations.models import Application, Language, RegistrationUpload
from apps.registrations.review_services import review_action
from apps.registrations.uploads import validate_upload

credentials = json.loads((ROOT / "artifacts/ui-credentials.json").read_text(encoding="utf-8"))
actor = get_user_model().objects.get(username=credentials["username"])
places = list(
    GramaPanchayat.objects.filter(active=True).exclude(
        pk__in=primary_appointments().values("panchayat_id")
    )[:2]
)


def application(place, name):
    app = Application.objects.create(
        application_number="GMF-REG-QA-" + uuid.uuid4().hex[:10],
        panchayat=place,
        full_name=name,
        normalized_name=name.lower(),
        mobile="9876543205",
        whatsapp="9876543205",
        address="Synthetic registry QA address",
        pin_code="695001",
        consent_version="1.0",
        consent_text=CONSENT,
        consented_at=timezone.now(),
    )
    app.languages.add(Language.objects.get(code="malayalam"))
    data = validate_upload(
        SimpleUploadedFile(
            "portrait.png",
            (ROOT / "artifacts/registration-test-photo.png").read_bytes(),
            content_type="image/png",
        ),
        max_bytes=5 * 1024 * 1024,
        photo=True,
    )
    RegistrationUpload.objects.create(
        application=app,
        slot="photo",
        file=data["content"],
        content_type=data["content_type"],
        byte_size=data["byte_size"],
        sha256=data["sha256"],
    )
    review_action(actor=actor, application_id=app.pk, action="start_review", revision=app.revision)
    app.refresh_from_db()
    return app


app = application(places[0], "Registry QA Facilitator")
review_action(
    actor=actor,
    application_id=app.pk,
    action="approve",
    revision=app.revision,
    reason="Synthetic browser test; verified duplicates.",
    verification_complete=True,
    acknowledge_duplicates=True,
)
f = app.facilitator
incoming = application(places[1], "Registry QA Successor")
(ROOT / "artifacts/registry-fixtures.json").write_text(
    json.dumps(
        {
            "id": str(f.pk),
            "number": f.facilitator_number,
            "source": places[0].pk,
            "destination": places[1].pk,
            "incoming": str(incoming.pk),
            "incoming_revision": incoming.revision,
        }
    ),
    encoding="utf-8",
)
print("Registry and replacement fixtures prepared in isolated QA storage.")
