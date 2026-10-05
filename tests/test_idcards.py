from datetime import timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pypdfium2 as pdfium
import zxingcpp
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.utils import timezone
from pypdf import PdfReader

from apps.audit.models import AuditLog
from apps.idcards.models import IdentityCard
from apps.idcards.services import card_state, download_card, issue_card, revoke_card
from apps.verification.services import rotate_token
from tests import test_registry as fixtures
from tests.factories import assign, user_with_role


class CardTests(TestCase):
    setUp = fixtures.RegistryTests.setUp
    make_app = fixtures.RegistryTests.make_app
    act = fixtures.RegistryTests.act
    begin = fixtures.RegistryTests.begin
    approve = fixtures.RegistryTests.approve
    change = fixtures.RegistryTests.change

    def issue(self, f=None, actor=None):
        f = f or self.approve()
        f.refresh_from_db()
        return issue_card(
            actor=actor or self.admin,
            facilitator_id=f.pk,
            revision=f.revision,
            reason="Verified card generation.",
        )

    def download(self, card, format="pdf"):
        card.facilitator.refresh_from_db()
        return download_card(
            actor=self.admin,
            card_id=card.pk,
            revision=card.facilitator.revision,
            reason="Authorized print",
            format=format,
        )[1]

    def test_issue_pdf_dimensions_privacy_and_both_qr_codes(self):
        card = self.issue()
        content = self.download(card)
        reader = PdfReader(BytesIO(content))
        self.assertEqual(len(reader.pages), 2)
        for page in reader.pages:
            self.assertAlmostEqual(float(page.mediabox.width), 85.6 * 72 / 25.4, places=3)
            self.assertAlmostEqual(float(page.mediabox.height), 54 * 72 / 25.4, places=3)
        text = " ".join(page.extract_text() for page in reader.pages)
        self.assertIn(card.facilitator.full_name, text)
        self.assertNotIn(card.facilitator.application.mobile, text)
        self.assertNotIn(card.facilitator.application.address, text)
        document = pdfium.PdfDocument(content)
        try:
            for page in document:
                bitmap = page.render(scale=4)
                decoded = zxingcpp.read_barcode(bitmap.to_pil())
                self.assertIsNotNone(decoded)
                self.assertIn("?card=" + card.public_token, decoded.text)
                self.assertIn("/verify/" + card.facilitator.verification_token + "/", decoded.text)
                bitmap.close()
                page.close()
        finally:
            document.close()
        self.assertEqual(card_state(card), "CURRENT")

    def test_a4_pdf_has_two_centered_print_pages(self):
        card = self.issue()
        reader = PdfReader(BytesIO(self.download(card, "print_pdf")))
        self.assertEqual(len(reader.pages), 2)
        for page in reader.pages:
            self.assertAlmostEqual(float(page.mediabox.width), 210 * 72 / 25.4, places=3)
            self.assertIn("100%", page.extract_text())

    def test_generation_retains_versions_and_supersedes_old(self):
        first = self.issue()
        second = self.issue(first.facilitator)
        first.refresh_from_db()
        self.assertEqual(first.status, "SUPERSEDED")
        self.assertEqual(second.version, 2)
        self.assertEqual(IdentityCard.objects.count(), 2)
        with self.assertRaises(ValidationError):
            self.download(first)

    def test_suspend_transfer_renew_and_rotation_disable_old_reprints(self):
        for action in ["suspend", "transfer", "renew", "rotate"]:
            with self.subTest(action=action):
                app = self.make_app(gp=self.other_gp if action == "renew" else self.gp, name=action)
                from apps.organization.models import SystemSetting

                policy = SystemSetting.objects.get(pk=1)
                policy.one_primary_per_panchayat = False
                policy.save()
                card = self.issue(self.approve(app))
                f = card.facilitator
                f.refresh_from_db()
                if action == "rotate":
                    rotate_token(
                        actor=self.admin,
                        facilitator_id=f.pk,
                        revision=f.revision,
                        reason="Token change",
                        confirmed=True,
                    )
                elif action == "transfer":
                    self.change(f, action, panchayat_id=self.other_gp.pk)
                elif action == "renew":
                    self.change(f, action, valid_until=f.valid_until + timedelta(days=1))
                else:
                    self.change(f, action)
                with self.assertRaises(ValidationError):
                    self.download(card)

    def test_revoked_card_scan_differs_from_active_identity(self):
        card = self.issue()
        f = card.facilitator
        f.refresh_from_db()
        revoke_card(actor=self.admin, card_id=card.pk, revision=f.revision, reason="Card lost")
        api = f"/api/v1/verify/{f.verification_token}/"
        data = self.client.get(api, {"card": card.public_token}).json()
        self.assertFalse(data["is_authorized"])
        self.assertEqual(data["card"]["status"], "REVOKED")
        self.assertEqual(data["identity_status"], "ACTIVE")
        self.assertTrue(self.client.get(api).json()["is_authorized"])
        self.assertEqual(self.client.get(api, {"card": "invalid"}).status_code, 404)

    def test_foreign_card_token_not_accepted(self):
        card = self.issue()
        other = self.approve(self.make_app(gp=self.other_gp))
        self.assertEqual(
            self.client.get(
                f"/api/v1/verify/{other.verification_token}/", {"card": card.public_token}
            ).status_code,
            404,
        )

    def test_nonactive_cannot_generate(self):
        f = self.change(self.approve(), "suspend")
        with self.assertRaises(ValidationError):
            self.issue(f)
        self.assertFalse(IdentityCard.objects.exists())

    def test_permissions_and_broader_view_do_not_expand_issue_scope(self):
        f = self.approve(self.make_app(gp=self.other_gp))
        assign(self.regional, "VIEWER", "STATE")
        for actor in [self.viewer, self.coordinator, self.reviewer, self.regional]:
            with self.assertRaises(PermissionDenied):
                self.issue(f, actor)
        operator = user_with_role("operator", "ID_CARD_OPERATOR", "DISTRICT", "KLM")
        self.assertEqual(self.issue(f, operator).generated_by, operator)

    def test_generation_revision_and_reason(self):
        f = self.approve()
        for revision, reason in [(0, "test"), (f.revision, "")]:
            with self.assertRaises(ValidationError):
                issue_card(actor=self.admin, facilitator_id=f.pk, revision=revision, reason=reason)
        self.assertFalse(IdentityCard.objects.exists())

    def test_audit_failure_cleans_new_files_and_preserves_old_version(self):
        first = self.issue()
        before = set(Path(self.media.name).rglob("*"))
        with patch("apps.idcards.services.record_event", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.issue(first.facilitator)
        self.assertEqual(
            set(p for p in Path(self.media.name).rglob("*") if p.is_file()),
            set(p for p in before if p.is_file()),
        )
        first.refresh_from_db()
        self.assertEqual(first.status, "ISSUED")
        self.assertEqual(IdentityCard.objects.count(), 1)

    def test_file_integrity_and_missing_portrait(self):
        f = self.approve()
        upload = f.application.uploads.get(slot="photo")
        Path(upload.file.path).write_bytes(b"altered")
        with self.assertRaises(ValidationError):
            self.issue(f)
        self.assertFalse(IdentityCard.objects.exists())

    def test_tampered_pdf_reprint_blocked(self):
        card = self.issue()
        Path(card.pdf.path).write_bytes(b"altered")
        with self.assertRaises(ValidationError):
            self.download(card)

    def test_revocation_and_reprint_reasons_audited(self):
        card = self.issue()
        self.download(card)
        self.assertEqual(
            AuditLog.objects.filter(action="card.reprinted", entity_id=str(card.pk)).count(), 1
        )
        f = card.facilitator
        f.refresh_from_db()
        with self.assertRaises(ValidationError):
            revoke_card(actor=self.admin, card_id=card.pk, revision=f.revision, reason="")
        revoke_card(actor=self.admin, card_id=card.pk, revision=f.revision, reason="Lost card")
        self.assertEqual(AuditLog.objects.filter(action="card.revoked").count(), 1)

    def test_http_views_csrf_and_no_public_artifacts(self):
        card = self.issue()
        f = card.facilitator
        self.assertEqual(self.client.get(f"/cards/{f.pk}/").status_code, 302)
        self.client.force_login(self.admin)
        for path in [
            f"/cards/{f.pk}/",
            f"/cards/{f.pk}/{card.pk}/",
            f"/cards/{f.pk}/generate/",
            f"/cards/{f.pk}/{card.pk}/actions/download/",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
        response = self.client.get(f"/cards/{f.pk}/{card.pk}/preview/front/")
        self.assertEqual(response.status_code, 200)
        response.close()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(
            client.post(f"/cards/{f.pk}/generate/", {"reason": "Test", "revision": 1}).status_code,
            403,
        )
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(f"/cards/{f.pk}/").status_code, 404)

    def test_expired_and_superseded_scan_states(self):
        first = self.issue()
        f = first.facilitator
        self.issue(f)
        data = self.client.get(
            f"/api/v1/verify/{f.verification_token}/", {"card": first.public_token}
        ).json()
        self.assertEqual(data["card"]["status"], "SUPERSEDED")
        latest = f.cards.first()
        latest.valid_until = timezone.localdate() - timedelta(days=1)
        latest.save()
        self.assertEqual(card_state(latest), "EXPIRED")

    def test_unsupported_font_characters_fail_without_artifacts(self):
        f = self.approve()
        f.full_name = "Unsupported 🛸"
        f.save()
        with self.assertRaises(ValidationError):
            self.issue(f)
        self.assertFalse(IdentityCard.objects.exists())

    def test_malayalam_name_renders_with_embedded_shaping_font(self):
        f = self.approve()
        f.full_name = "അചൽ കുമാർ"
        f.save()
        card = self.issue(f)
        self.assertEqual(card.snapshot["name"], f.full_name)
        self.assertTrue(card.pdf.storage.exists(card.pdf.name))

    def test_card_operator_cannot_revoke_without_management_permission(self):
        card = self.issue()
        operator = user_with_role("cardstaff", "ID_CARD_OPERATOR", "DISTRICT", "TVM")
        card.facilitator.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            revoke_card(
                actor=operator,
                card_id=card.pk,
                revision=card.facilitator.revision,
                reason="Not authorized",
            )
        self.client.force_login(operator)
        self.assertEqual(
            self.client.get(f"/cards/{card.facilitator_id}/{card.pk}/actions/revoke/").status_code,
            403,
        )
