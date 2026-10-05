"""Create an isolated, disposable UI-check database. Never modifies the main database."""

import json
import os
import secrets
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
artifacts = ROOT / "artifacts"
artifacts.mkdir(exist_ok=True)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
os.environ["DATABASE_URL"] = f"sqlite:///{(artifacts / 'ui.sqlite3').as_posix()}"
os.environ["DEBUG"] = "True"
import django  # noqa: E402

django.setup()
from django.core.management import call_command  # noqa: E402

from apps.accounts.models import User  # noqa: E402

call_command("migrate", verbosity=0)
call_command("seed_kerala_locations", verbosity=0)
password = secrets.token_urlsafe(24)
user, _ = User.objects.get_or_create(
    username="ui-check", defaults={"email": "ui-check@example.invalid"}
)
user.is_superuser = True
user.is_staff = True
user.first_name = "Workspace"
user.last_name = "Administrator"
user.set_password(password)
user.save()
(artifacts / "ui-credentials.json").write_text(
    json.dumps({"username": user.username, "password": password}), encoding="utf-8"
)
print("Isolated UI database prepared. Credentials are in the ignored artifacts directory.")

# Non-personal file fixtures used only by the isolated registration browser check.

image = Image.new("RGB", (600, 800), (40, 110, 90))
draw = ImageDraw.Draw(image)
draw.ellipse((160, 110, 440, 390), fill=(220, 210, 180))
draw.rounded_rectangle((100, 410, 500, 760), 40, fill=(20, 55, 80))
image.save(artifacts / "registration-test-photo.png")
writer = PdfWriter()
writer.add_blank_page(width=300, height=400)
writer.write(artifacts / "registration-test.pdf")
