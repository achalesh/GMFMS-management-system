# ruff: noqa: E402
"""Prepare private/public verification browser assertions in QA storage only."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'artifacts/ui.sqlite3').as_posix()}"
os.environ["MEDIA_ROOT"] = "artifacts/ui-media"
import django

django.setup()
from apps.facilitators.models import Facilitator
from apps.organization.models import SystemSetting

fixtures = json.loads((ROOT / "artifacts/registry-fixtures.json").read_text(encoding="utf-8"))
f = Facilitator.objects.get(pk=fixtures["id"])
app = f.application
app.address = "NEVER PUBLIC HOME ADDRESS"
app.email = "never-public-contact@example.org"
app.emergency_name = "NEVER PUBLIC EMERGENCY PERSON"
app.emergency_mobile = "9123456789"
app.public_mobile_consent = False
app.public_email_consent = False
app.public_social_consent = False
app.save()
policy = SystemSetting.objects.get(pk=1)
policy.allow_public_mobile = True
policy.allow_public_email = True
policy.allow_public_social_profiles = True
policy.save()
(ROOT / "artifacts/verification-fixtures.json").write_text(
    json.dumps(
        {
            "id": str(f.pk),
            "token": f.verification_token,
            "number": f.facilitator_number,
            "name": f.full_name,
            "mobile": app.mobile,
            "email": app.email,
            "address": app.address,
            "emergency": app.emergency_name,
        }
    ),
    encoding="utf-8",
)
print(
    "Verification fixtures prepared in isolated QA database; private sentinel values will be checked for leaks."
)
