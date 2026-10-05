import hashlib
import json
import logging
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import zxingcpp
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from apps.audit.models import AuditLog
from apps.organization.models import SystemSetting
from apps.verification.logging import RedactVerificationToken
from apps.verification.models import VerificationTokenHistory
from apps.verification.projection import public_profile
from apps.verification.services import qr_png, rotate_token, verification_url
from tests import test_registry as registry_fixtures
from tests.factories import assign, user_with_role


class VerificationTests(TestCase):
    setUp = registry_fixtures.RegistryTests.setUp
    make_app = registry_fixtures.RegistryTests.make_app
    act = registry_fixtures.RegistryTests.act
    begin = registry_fixtures.RegistryTests.begin
    approve = registry_fixtures.RegistryTests.approve
    change = registry_fixtures.RegistryTests.change
    incoming = registry_fixtures.RegistryTests.incoming

    def endpoints(self, token):
        return [f"/verify/{token}/", f"/api/v1/verify/{token}/", f"/verify/{token}/portrait/"]

    def policy(self, **values):
        policy = SystemSetting.objects.get(pk=1)
        for key, value in values.items():
            setattr(policy, key, value)
        policy.save()

    def test_public_projection_exact_allowlist(self):
        f = self.approve()
        data = self.client.get(f"/api/v1/verify/{f.verification_token}/").json()
        self.assertEqual(
            set(data),
            {
                "name",
                "name_ml",
                "facilitator_id",
                "role",
                "panchayat",
                "block",
                "district",
                "status",
                "status_label",
                "is_authorized",
                "valid_until",
                "updated_at",
                "portrait_url",
                "organization",
            },
        )
        self.assertEqual(set(data["organization"]), {"name", "short_name", "network_name"})
        self.assertEqual(data["status"], "ACTIVE")
        self.assertTrue(data["is_authorized"])
        self.assertEqual(data["facilitator_id"], f.facilitator_number)

    def test_private_fields_absent_from_html_and_json_even_for_admin(self):
        f = self.approve()
        self.app.refresh_from_db()
        self.app.email = "private-person@example.org"
        self.app.address = "SECRET HOME ADDRESS"
        self.app.emergency_name = "SECRET EMERGENCY NAME"
        self.app.emergency_mobile = "9123456789"
        self.app.date_of_birth = "1991-02-03"
        self.app.social_profiles = {"facebook": "https://example.org/private-profile"}
        self.app.save()
        for login in [False, True]:
            if login:
                self.client.force_login(self.admin)
            for path in self.endpoints(f.verification_token)[:2]:
                response = self.client.get(path, {"fields": "__all__", "include_private": "true"})
                self.assertEqual(response.status_code, 200)
                for secret in [
                    str(f.pk),
                    str(self.app.pk),
                    self.app.application_number,
                    self.app.email,
                    self.app.address,
                    self.app.emergency_name,
                    self.app.emergency_mobile,
                    "1991-02-03",
                    self.app.mobile,
                    "private-profile",
                    "Verified test record.",
                ]:
                    self.assertNotContains(response, secret)

    def test_contacts_require_both_policy_and_individual_consent(self):
        f = self.approve()
        for policy, consent in [(False, False), (True, False), (False, True), (True, True)]:
            self.policy(
                allow_public_mobile=policy,
                allow_public_email=policy,
                allow_public_social_profiles=policy,
            )
            app = f.application
            app.public_mobile_consent = consent
            app.public_email_consent = consent
            app.public_social_consent = consent
            app.email = "permitted@example.org"
            app.social_profiles = {"instagram": "https://example.org/profile"}
            app.save()
            data = self.client.get(f"/api/v1/verify/{f.verification_token}/").json()
            for field in ["mobile", "email", "social_profiles"]:
                self.assertEqual(field in data, policy and consent)

    def test_nonactive_status_never_publishes_optional_contacts(self):
        f = self.approve()
        self.policy(allow_public_mobile=True)
        f.application.public_mobile_consent = True
        f.application.save()
        for status in ["SUSPENDED", "INACTIVE", "REVOKED", "REPLACED", "EXPIRED"]:
            f.status = status
            f.save()
            data = self.client.get(f"/api/v1/verify/{f.verification_token}/").json()
            self.assertEqual(data["status"], status)
            self.assertFalse(data["is_authorized"])
            self.assertNotIn("mobile", data)
            response = self.client.get(f"/verify/{f.verification_token}/")
            self.assertContains(response, "not currently authorized")
            self.assertNotContains(response, "Verified Media Facilitator")

    def test_expiry_without_maintenance_is_immediate(self):
        f = self.approve()
        f.valid_until = timezone.localdate() - timedelta(days=1)
        f.save()
        self.assertEqual(public_profile(f)["status"], "EXPIRED")
        f.valid_until = timezone.localdate()
        f.save()
        self.assertEqual(public_profile(f)["status"], "ACTIVE")

    def test_expired_appointment_and_future_or_ended_appointments_are_not_active(self):
        f = self.approve()
        a = f.current_appointment
        a.effective_to = timezone.localdate() - timedelta(days=1)
        a.save()
        self.assertEqual(public_profile(f)["status"], "EXPIRED")
        a.effective_to = f.valid_until
        a.effective_from = timezone.localdate() + timedelta(days=1)
        a.save()
        self.assertEqual(public_profile(f)["status"], "INACTIVE")
        a.effective_from = timezone.localdate()
        a.ended_at = timezone.now()
        a.save()
        self.assertEqual(public_profile(f)["status"], "INACTIVE")

    def test_inactive_location_ancestry_fails_closed(self):
        f = self.approve()
        p = f.current_appointment.panchayat
        for obj in [p, p.block, p.block.district, p.block.district.state]:
            obj.active = False
            obj.save()
            data = self.client.get(f"/api/v1/verify/{f.verification_token}/").json()
            self.assertEqual(data["status"], "INACTIVE")
            obj.active = True
            obj.save()

    def test_unknown_status_or_missing_appointment_fails_closed(self):
        f = self.approve()
        f.status = "UNKNOWN"
        f.save()
        self.assertEqual(public_profile(f)["status"], "INACTIVE")
        f.current_appointment = None
        f.status = "ACTIVE"
        f.save()
        self.assertEqual(public_profile(f)["status"], "INACTIVE")

    def test_invalid_tokens_have_generic_responses(self):
        f = self.approve()
        for token in ["bad", "a" * 43, "a" * 65, str(f.pk), f.facilitator_number]:
            for path in self.endpoints(token):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, f.full_name, status_code=404)
        data = self.client.get("/api/v1/verify/invalid/").json()
        self.assertEqual(data, {"error": "Verification unavailable"})

    def test_unapproved_application_never_verifies(self):
        f = self.approve()
        f.application.status = "REJECTED"
        f.application.save()
        for path in self.endpoints(f.verification_token):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_public_directory_disabled_does_not_disable_token_verification(self):
        f = self.approve()
        self.policy(public_directory_enabled=False)
        self.assertEqual(self.client.get(f"/verify/{f.verification_token}/").status_code, 200)
        self.assertEqual(self.client.get("/verify/").status_code, 404)

    def test_portrait_only_private_documents_have_no_public_path(self):
        f = self.approve()
        response = self.client.get(f"/verify/{f.verification_token}/portrait/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/jpeg")
        content = b"".join(response.streaming_content)
        with Image.open(BytesIO(content)) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertFalse(image.getexif())
        for route in ["documents", "files", "identity", "photo/../documents"]:
            self.assertEqual(
                self.client.get(f"/verify/{f.verification_token}/{route}/").status_code, 404
            )

    def test_missing_portrait_returns_generic_404(self):
        f = self.approve()
        upload = f.application.uploads.get(slot="photo")
        upload.file.delete(save=False)
        self.assertEqual(
            self.client.get(f"/verify/{f.verification_token}/portrait/").status_code, 404
        )

    def test_public_headers_and_methods(self):
        f = self.approve()
        for path in self.endpoints(f.verification_token):
            response = self.client.get(path)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["Referrer-Policy"], "no-referrer")
            self.assertIn("noindex", response["X-Robots-Tag"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
            response.close()
            self.assertEqual(self.client.post(path).status_code, 405)

    def test_shared_page_and_api_rate_limit(self):
        f = self.approve()
        with patch("apps.verification.views.consume_budget", return_value=False):
            for path in self.endpoints(f.verification_token):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response["Retry-After"], "3600")
                self.assertNotContains(response, f.full_name, status_code=429)
        from django.test import RequestFactory

        from apps.registrations.security import consume_budget

        request = RequestFactory().get("/verify/invalid/", REMOTE_ADDR="192.0.2.22")
        for _ in range(120):
            self.assertTrue(consume_budget(request, "verification-lookup", 120))
        self.assertFalse(consume_budget(request, "verification-lookup", 120))

    def test_social_allowlist_rejects_active_urls_credentials_and_unknown_keys(self):
        f = self.approve()
        self.policy(allow_public_social_profiles=True)
        f.application.public_social_consent = True
        f.application.social_profiles = {
            "facebook": "javascript:alert(1)",
            "instagram": "https://user:password@example.org/",
            "youtube": "https://example.org/channel",
            "secret": "https://example.org/secret",
        }
        f.application.save()
        self.assertEqual(
            public_profile(f)["social_profiles"], {"youtube": "https://example.org/channel"}
        )

    def test_html_escapes_identity_values(self):
        f = self.approve()
        f.full_name = '<script>alert("x")</script>'
        f.save()
        response = self.client.get(f"/verify/{f.verification_token}/")
        self.assertNotContains(response, "<script>")
        self.assertContains(response, "&lt;script&gt;")

    @override_settings(PUBLIC_BASE_URL="https://media.example.org")
    def test_generated_qr_roundtrip_contains_only_verification_url(self):
        f = self.approve()
        url = verification_url(f)
        png = qr_png(url)
        with Image.open(BytesIO(png)) as image:
            decoded = zxingcpp.read_barcode(image)
            self.assertIsNotNone(decoded)
            self.assertEqual(decoded.text, url)
            self.assertLess(image.width, 1000)
        self.assertEqual(url, f"https://media.example.org/verify/{f.verification_token}/")
        self.assertNotIn(str(f.pk), url)
        self.assertNotIn(f.application.mobile, url)

    def test_qr_source_uses_configured_origin_not_request_host(self):
        f = self.approve()
        self.client.force_login(self.admin)
        with override_settings(PUBLIC_BASE_URL="https://media.example.org"):
            response = self.client.get(f"/verification/{f.pk}/qr.png", HTTP_HOST="localhost")
            decoded = zxingcpp.read_barcode(Image.open(BytesIO(response.content)))
            self.assertTrue(decoded.text.startswith("https://media.example.org/verify/"))
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["Content-Type"], "image/png")

    def test_qr_view_permission_and_scope(self):
        f = self.approve()
        other = self.approve(self.make_app(gp=self.other_gp))
        self.assertEqual(self.client.get(f"/verification/{f.pk}/").status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(f"/verification/{f.pk}/").status_code, 403)
        operator = user_with_role("operator", "ID_CARD_OPERATOR", "DISTRICT", "TVM")
        self.client.force_login(operator)
        self.assertEqual(self.client.get(f"/verification/{f.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/verification/{other.pk}/qr.png").status_code, 404)
        self.assertEqual(self.client.get(f"/verification/{f.pk}/rotate/").status_code, 404)

    def test_invalid_public_origin_is_rejected(self):
        f = self.approve()
        for base in [
            "javascript:bad",
            "https://user:secret@example.org",
            "https://example.org/?query=1",
            "https://example.org/subpath",
            "https://example.org/#fragment",
        ]:
            with override_settings(PUBLIC_BASE_URL=base):
                with self.assertRaises(ValidationError):
                    verification_url(f)

    def test_rotation_invalidates_old_html_api_portrait_and_preserves_identity(self):
        f = self.approve()
        old = f.verification_token
        appointment = f.current_appointment_id
        number = f.facilitator_number
        f = rotate_token(
            actor=self.admin,
            facilitator_id=f.pk,
            revision=f.revision,
            reason="Lost QR replacement",
            confirmed=True,
        )
        self.assertNotEqual(f.verification_token, old)
        self.assertEqual((f.current_appointment_id, f.facilitator_number), (appointment, number))
        for path in self.endpoints(old):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get(f"/verify/{f.verification_token}/").status_code, 200)
        history = f.token_history.get()
        self.assertEqual(history.previous_digest, hashlib.sha256(old.encode()).hexdigest())
        events = json.dumps(
            list(
                AuditLog.objects.filter(entity_id=str(f.pk)).values(
                    "old_values", "new_values", "reason"
                )
            )
        )
        self.assertNotIn(old, events)
        self.assertNotIn(f.verification_token, events)

    def test_rotation_permission_revision_and_confirmation(self):
        f = self.approve()
        for actor in [self.viewer, self.reviewer, self.coordinator]:
            with self.assertRaises(PermissionDenied):
                rotate_token(
                    actor=actor,
                    facilitator_id=f.pk,
                    revision=f.revision,
                    reason="Test",
                    confirmed=True,
                )
        for revision, reason, confirmed in [
            (0, "Test", True),
            (f.revision, "", True),
            (f.revision, "Test", False),
        ]:
            with self.assertRaises(ValidationError):
                rotate_token(
                    actor=self.admin,
                    facilitator_id=f.pk,
                    revision=revision,
                    reason=reason,
                    confirmed=confirmed,
                )
        self.assertFalse(VerificationTokenHistory.objects.exists())

    def test_broader_view_cannot_rotate_other_district(self):
        f = self.approve(self.make_app(gp=self.other_gp))
        assign(self.regional, "VIEWER", "STATE")
        with self.assertRaises(PermissionDenied):
            rotate_token(
                actor=self.regional,
                facilitator_id=f.pk,
                revision=f.revision,
                reason="Test",
                confirmed=True,
            )

    def test_rotation_rollback_and_append_only_history(self):
        f = self.approve()
        old = f.verification_token
        with patch("apps.verification.services.record_event", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                rotate_token(
                    actor=self.admin,
                    facilitator_id=f.pk,
                    revision=f.revision,
                    reason="Test",
                    confirmed=True,
                )
        f.refresh_from_db()
        self.assertEqual(f.verification_token, old)
        self.assertFalse(f.token_history.exists())
        f = rotate_token(
            actor=self.admin,
            facilitator_id=f.pk,
            revision=f.revision,
            reason="Test",
            confirmed=True,
        )
        history = f.token_history.get()
        with self.assertRaises(ValidationError):
            history.save()
        with self.assertRaises(ValidationError):
            history.delete()
        with self.assertRaises(ValidationError):
            f.token_history.update(reason="changed")

    def test_rotation_requires_csrf_and_get_is_readonly(self):
        f = self.approve()
        old = f.verification_token
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(f"/verification/{f.pk}/rotate/").status_code, 200)
        f.refresh_from_db()
        self.assertEqual(f.verification_token, old)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(
            client.post(
                f"/verification/{f.pk}/rotate/",
                {"revision": f.revision, "reason": "Test", "confirmed": "on"},
            ).status_code,
            403,
        )

    def test_replacement_keeps_old_token_showing_replaced(self):
        f = self.approve()
        old = f.verification_token
        incoming = self.incoming()
        self.change(
            f,
            "replace",
            replacement_id=incoming.pk,
            application_revision=incoming.revision,
            verification_complete=True,
            acknowledge_duplicates=True,
        )
        data = self.client.get(f"/api/v1/verify/{old}/").json()
        self.assertEqual(data["status"], "REPLACED")
        self.assertFalse(data["is_authorized"])

    def test_transfer_updates_public_location_without_rotating_token(self):
        f = self.approve()
        old = f.verification_token
        self.change(f, "transfer", panchayat_id=self.other_gp.pk)
        data = self.client.get(f"/api/v1/verify/{old}/").json()
        self.assertEqual(data["panchayat"], self.other_gp.name_en)
        self.assertEqual(data["status"], "ACTIVE")

    def test_public_lookup_does_not_write_personal_scan_audit(self):
        f = self.approve()
        before = AuditLog.objects.count()
        self.client.get(f"/verify/{f.verification_token}/")
        self.assertEqual(AuditLog.objects.count(), before)

    def test_request_logging_redacts_token(self):
        token = "secret_random_verification_token_here"
        for path in [f"/verify/{token}/", f"/api/v1/verify/{token}/", f"/verify/{token}/portrait/"]:
            record = logging.LogRecord(
                "django.server", logging.INFO, "", 1, '"GET %s HTTP/1.1" 200', (path,), None
            )
            RedactVerificationToken().filter(record)
            self.assertNotIn(token, record.getMessage())
            self.assertIn("[redacted]", record.getMessage())

    @override_settings(DEBUG=True)
    def test_public_failure_never_displays_debug_private_data(self):
        f = self.approve()
        with patch(
            "apps.verification.views.public_profile",
            side_effect=RuntimeError("PRIVATE INTERNAL CONTACT"),
        ):
            for path in self.endpoints(f.verification_token)[:2]:
                response = self.client.get(path)
                self.assertEqual(response.status_code, 503)
                self.assertNotContains(response, "PRIVATE INTERNAL CONTACT", status_code=503)
                self.assertNotContains(response, self.app.mobile, status_code=503)
                self.assertIn("no-store", response["Cache-Control"])

    def test_budget_storage_failure_is_private_service_unavailable(self):
        with patch(
            "apps.verification.views.consume_budget",
            side_effect=RuntimeError("Database credentials"),
        ):
            response = self.client.get("/api/v1/verify/invalid/")
            self.assertEqual(response.status_code, 503)
            self.assertNotContains(response, "Database credentials", status_code=503)
