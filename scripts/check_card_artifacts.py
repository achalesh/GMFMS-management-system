# ruff: noqa: E402
"""Validate and render only synthetic QA card PDFs; never use the real database."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

import pypdfium2 as pdfium
import zxingcpp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'artifacts/ui.sqlite3').as_posix()}"
os.environ["MEDIA_ROOT"] = "artifacts/ui-media"
os.environ["PUBLIC_BASE_URL"] = "http://127.0.0.1:8001"
import django

django.setup()
from apps.facilitators.models import Facilitator
from apps.idcards.rendering import render_cards
from apps.idcards.services import source

fixture = json.loads((ROOT / "artifacts/registry-fixtures.json").read_text(encoding="utf-8"))
f = Facilitator.objects.get(pk=fixture["id"])
snapshot, _, upload = source(f)
url = snapshot.pop("verification_url")
snapshot.update(
    name="അചൽ കുമാർ", version=99, card_number="QA-MALAYALAM-SAMPLE", issue_date="2026-09-29"
)
with upload.file.open("rb") as stream:
    portrait = stream.read()
rendered = render_cards(snapshot, portrait, url + "?card=synthetic-visual-proof-only")
(ROOT / "artifacts/card-malayalam.pdf").write_bytes(rendered["pdf"])
(ROOT / "artifacts/card-malayalam-front.png").write_bytes(rendered["front"])
for filename in ["card-size.pdf", "card-a4.pdf"]:
    doc = pdfium.PdfDocument(str(ROOT / "artifacts" / filename))
    try:
        for page in doc:
            bitmap = page.render(scale=4)
            result = zxingcpp.read_barcode(bitmap.to_pil())
            assert result and "?card=" in result.text
            parsed = urlsplit(result.text)
            with urlopen(
                "http://127.0.0.1:8001/api/v1" + parsed.path + "?" + parsed.query
            ) as response:
                data = json.load(response)
                assert data["card"]["status"] == "SUPERSEDED"
                assert not data["is_authorized"]
            bitmap.close()
            page.close()
    finally:
        doc.close()
print(
    "Both PDF formats decode on both sides and scans reject superseded cards. Malayalam visual proof rendered."
)
