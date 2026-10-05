import logging
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.files.uploadhandler import StopUpload
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.accounts.checks import storage_and_browser_checks
from apps.common.middleware import BrowserSecurityMiddleware
from apps.registrations.security import consume_budget, staff_budget
from apps.registrations.upload_handlers import RegistrationUploadLimitHandler
from apps.verification.logging import RedactVerificationToken
from tests import test_registry as fixtures
from tests.factories import user_with_role


class BrowserAndUploadTests(SimpleTestCase):
    def test_stream_limits_apply_to_corrections_and_unknown_upload_routes(self):
        for path in ["/correct/abc/edit/", "/register/media-facilitator/step/5/", "/unknown/"]:
            request = RequestFactory().post(path)
            handler = RegistrationUploadLimitHandler(request)
            handler.current = 20 * 1024 * 1024
            with self.assertRaises(StopUpload):
                handler.receive_data_chunk(b"x", 0)
            self.assertTrue(request.registration_upload_rejected)

    def test_import_has_tighter_limit(self):
        request = RequestFactory().post("/locations/import/")
        handler = RegistrationUploadLimitHandler(request)
        handler.current = 5 * 1024 * 1024
        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b"x", 0)

    def test_total_upload_and_file_count_limits(self):
        request = RequestFactory().post("/correct/abc/edit/")
        handler = RegistrationUploadLimitHandler(request)
        handler.total = 100 * 1024 * 1024
        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b"x", 0)
        handler = RegistrationUploadLimitHandler(request)
        handler.files = 9
        with self.assertRaises(StopUpload):
            handler.new_file("f", "file.pdf", "application/pdf", 1)

    def test_truncated_multipart_never_reaches_view(self):
        request = RequestFactory().post("/correct/abc/edit/", {"name": "partial"})
        request.registration_upload_rejected = True
        middleware = BrowserSecurityMiddleware(lambda r: HttpResponse("unexpected"))
        self.assertEqual(middleware.process_view(request, None, (), {}).status_code, 413)

    def test_reset_verification_and_query_tokens_redacted(self):
        record = logging.LogRecord(
            "django.server",
            20,
            "",
            0,
            "GET %s",
            ("/accounts/password/reset/dXNlcg/secret-reset/?token=secret-query&card=secret-card",),
            None,
        )
        RedactVerificationToken().filter(record)
        self.assertNotIn("secret", record.getMessage())
        self.assertNotIn("dXNlcg", record.getMessage())
        record = logging.LogRecord(
            "django.server", 20, "", 0, "GET /verify/secret-verify/?card=secret-card", (), None
        )
        RedactVerificationToken().filter(record)
        self.assertNotIn("secret", record.getMessage())

    @override_settings(
        MEDIA_ROOT=settings.STATIC_ROOT / "private",
        SESSION_COOKIE_HTTPONLY=False,
        CORS_ALLOW_ALL_ORIGINS=True,
        CSRF_TRUSTED_ORIGINS=["http://example.org"],
    )
    def test_deployment_checks_fail_for_unsafe_storage_and_cookies(self):
        self.assertEqual(
            {e.id for e in storage_and_browser_checks(None)},
            {"gmfms.E001", "gmfms.E002", "gmfms.E003", "gmfms.E004"},
        )

    def test_current_storage_and_cookie_checks_pass(self):
        self.assertEqual(storage_and_browser_checks(None), [])


class SessionAndBudgetTests(TestCase):
    def setUp(self):
        self.user = user_with_role("hardening", "SUPER_ADMIN")

    def test_security_headers_on_login_and_staff_pages(self):
        for path in ["/accounts/login/", "/register/media-facilitator/"]:
            r = self.client.get(path)
            self.assertIn("script-src 'self'", r["Content-Security-Policy"])
            self.assertNotIn("script-src 'self' 'unsafe-inline'", r["Content-Security-Policy"])
            self.assertEqual(r["Referrer-Policy"], "same-origin")
            self.assertEqual(r["X-Frame-Options"], "DENY")
        self.client.force_login(self.user)
        self.assertIn("no-store", self.client.get("/reports/")["Cache-Control"])

    def test_login_rotates_session_and_logout_invalidates_it(self):
        session = self.client.session
        session["test"] = "old"
        session.save()
        old = session.session_key
        self.client.post(
            "/accounts/login/",
            {"username": self.user.username, "password": "Uncommon-test-password-729!"},
        )
        self.assertNotEqual(self.client.session.session_key, old)
        session_key = self.client.session.session_key
        self.client.post("/accounts/logout/")
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertEqual(self.client.get("/reports/").status_code, 302)

    def test_expired_and_disabled_sessions_deny_access(self):
        self.client.force_login(self.user)
        Session.objects.filter(session_key=self.client.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(self.client.get("/reports/").status_code, 302)
        self.client.force_login(self.user)
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get("/reports/").status_code, 302)

    def test_staff_budget_shared_across_ips_but_not_accounts(self):
        other = user_with_role("other-admin", "SUPER_ADMIN")
        calls = []

        @staff_budget("test-expensive", 1)
        def view(request):
            calls.append(True)
            return HttpResponse("ok")

        def request(user, ip):
            r = RequestFactory().post("/reports/", REMOTE_ADDR=ip)
            r.user = user
            return r

        self.assertEqual(view(request(self.user, "192.0.2.1")).status_code, 200)
        limited = view(request(self.user, "192.0.2.2"))
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited["Retry-After"], "3600")
        self.assertEqual(view(request(other, "192.0.2.1")).status_code, 200)
        self.assertEqual(len(calls), 2)

    def test_forwarded_headers_cannot_bypass_ip_budget(self):
        r = RequestFactory().get("/", REMOTE_ADDR="192.0.2.1", HTTP_X_FORWARDED_FOR="192.0.2.2")
        self.assertTrue(consume_budget(r, "test-ip", 1))
        r.META["HTTP_X_FORWARDED_FOR"] = "192.0.2.3"
        self.assertFalse(consume_budget(r, "test-ip", 1))

    def test_export_budget_rejects_before_rendering(self):
        self.client.force_login(self.user)
        with (
            patch("apps.registrations.security.consume_budget", return_value=False),
            patch("apps.reports.views.report_data") as data,
        ):
            r = self.client.post("/reports/", {"format": "pdf", "reason": "Budget regression"})
            self.assertEqual(r.status_code, 429)
            data.assert_not_called()


class PermissionAndLeakageTests(TestCase):
    setUp = fixtures.RegistryTests.setUp
    make_app = fixtures.RegistryTests.make_app
    act = fixtures.RegistryTests.act
    begin = fixtures.RegistryTests.begin
    approve = fixtures.RegistryTests.approve
    change = fixtures.RegistryTests.change

    def test_anonymous_private_route_matrix(self):
        f = self.approve()
        for path in [
            f"/facilitators/{f.pk}/",
            f"/cards/{f.pk}/",
            f"/verification/{f.pk}/",
            f"/applications/{self.app.pk}/",
            "/reports/",
            "/audit/",
            "/settings/system/",
        ]:
            self.assertEqual(self.client.get(path).status_code, 302, path)
        for path in [
            "/private-media/test.pdf",
            "/.env",
            "/db.sqlite3",
            "/artifacts/ui-credentials.json",
        ]:
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_cross_district_private_route_matrix(self):
        f = self.approve(self.make_app(gp=self.other_gp, name="Outside secret applicant"))
        self.client.force_login(self.regional)
        for path in [
            f"/facilitators/{f.pk}/",
            f"/cards/{f.pk}/",
            f"/verification/{f.pk}/",
            f"/applications/{f.application_id}/",
        ]:
            r = self.client.get(path)
            self.assertEqual(r.status_code, 404, path)
            self.assertNotIn(b"Outside secret applicant", r.content)

    def test_public_fields_cannot_be_expanded_by_staff_login_or_query(self):
        f = self.approve()
        self.client.force_login(self.admin)
        r = self.client.get(
            f"/api/v1/verify/{f.verification_token}/?fields=__all__&include_private=true"
        )
        self.assertEqual(r.status_code, 200)
        for secret in [
            str(f.pk),
            "9876543210",
            "Private home address",
            "verification_token",
            "consent_text",
            "uploaded_documents",
            "date_of_birth",
        ]:
            self.assertNotIn(secret, r.content.decode())
        self.assertIn("default-src 'none'", r["Content-Security-Policy"])

    def test_csrf_required_for_sensitive_write_matrix(self):
        f = self.approve()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for path in [
            f"/cards/{f.pk}/generate/",
            f"/verification/{f.pk}/rotate/",
            "/reports/",
            "/settings/system/",
            f"/facilitators/{f.pk}/actions/suspend/",
        ]:
            self.assertEqual(client.post(path, {}).status_code, 403, path)
