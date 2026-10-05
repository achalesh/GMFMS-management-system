import re
from datetime import timedelta

from axes.models import AccessAttempt
from django.contrib.auth.password_validation import validate_password
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.audit.models import AuditLog

from .factories import user_with_role


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = user_with_role("staff")
        cls.password = "Uncommon-test-password-729!"

    def test_anonymous_redirect_and_api_denied(self):
        self.assertRedirects(self.client.get("/"), "/accounts/login/?next=/")
        for path in ["/api/v1/auth/me/", "/api/schema/", "/api/docs/"]:
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_login_and_post_logout_audited(self):
        response = self.client.post(
            "/accounts/login/", {"username": "staff", "password": self.password}
        )
        self.assertRedirects(response, "/")
        self.assertTrue(AuditLog.objects.filter(action="auth.login", user=self.user).exists())
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        self.assertRedirects(self.client.post("/accounts/logout/"), "/accounts/login/")
        self.assertTrue(AuditLog.objects.filter(action="auth.logout").exists())

    def test_login_redirect_cannot_leave_site(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": "staff", "password": self.password, "next": "https://evil.example/"},
        )
        self.assertEqual(response.url, "/")

    def test_csrf_login_and_settings_and_logout(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            client.post(
                "/accounts/login/", {"username": "staff", "password": self.password}
            ).status_code,
            403,
        )
        client.force_login(self.user)
        self.assertEqual(client.post("/settings/system/", {}).status_code, 403)
        self.assertEqual(client.post("/accounts/logout/").status_code, 403)

    def test_wrong_password_is_generic_and_never_echoed(self):
        response = self.client.post(
            "/accounts/login/", {"username": "not-a-user", "password": "Sensitive-input"}
        )
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotContains(response, "Sensitive-input")

    def test_lockout_is_enforced_even_for_correct_password(self):
        for _ in range(5):
            response = self.client.post(
                "/accounts/login/", {"username": "staff", "password": "wrong"}
            )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            self.client.post(
                "/accounts/login/", {"username": "staff", "password": self.password}
            ).status_code,
            429,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lockout_expires(self):
        for _ in range(5):
            self.client.post("/accounts/login/", {"username": "staff", "password": "wrong"})
        AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=20))
        self.assertEqual(
            self.client.post(
                "/accounts/login/", {"username": "staff", "password": self.password}
            ).status_code,
            302,
        )

    def test_username_lockout_cannot_be_bypassed_by_new_ip(self):
        for _ in range(5):
            self.client.post(
                "/accounts/login/",
                {"username": "staff", "password": "wrong"},
                REMOTE_ADDR="127.0.0.2",
            )
        response = self.client.post(
            "/accounts/login/",
            {"username": "staff", "password": self.password},
            REMOTE_ADDR="127.0.0.3",
        )
        self.assertEqual(response.status_code, 429)

    def test_inactive_account_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(
            self.client.post(
                "/accounts/login/", {"username": "staff", "password": self.password}
            ).status_code,
            200,
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_strength(self):
        for password in ["short", "12345678901234", "passwordpassword"]:
            with self.assertRaises(ValidationError):
                validate_password(password, self.user)

    def test_password_change_audited(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/accounts/password/change/",
            {
                "old_password": self.password,
                "new_password1": "Different-passphrase-874!",
                "new_password2": "Different-passphrase-874!",
            },
        )
        self.assertRedirects(response, "/")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Different-passphrase-874!"))
        self.assertTrue(AuditLog.objects.filter(action="auth.password_changed").exists())

    def test_reset_does_not_disclose_account_existence(self):
        known = self.client.post("/accounts/password/reset/", {"email": self.user.email})
        unknown = self.client.post("/accounts/password/reset/", {"email": "unknown@example.org"})
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.url, unknown.url)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_token_is_single_use_and_audited(self):
        self.client.post("/accounts/password/reset/", {"email": self.user.email})
        url = re.search(r"http://testserver([^\s]+)", mail.outbox[0].body).group(1)
        redirect = self.client.get(url)
        self.assertEqual(redirect.status_code, 302)
        response = self.client.post(
            redirect.url,
            {
                "new_password1": "New-reset-passphrase-983!",
                "new_password2": "New-reset-passphrase-983!",
            },
        )
        self.assertRedirects(response, "/accounts/password/reset/complete/")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("New-reset-passphrase-983!"))
        self.assertTrue(AuditLog.objects.filter(action="auth.password_reset").exists())
        self.assertContains(self.client.get(url), "invalid or has expired")

    def test_reset_throttling(self):
        for _ in range(5):
            self.assertEqual(
                self.client.post(
                    "/accounts/password/reset/", {"email": "unknown@example.org"}
                ).status_code,
                302,
            )
        response = self.client.post("/accounts/password/reset/", {"email": "unknown@example.org"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "900")

    def test_api_is_minimal_and_private_responses_not_cached(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(set(response.json()), {"username", "display_name", "preferred_language"})
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("no-store", self.client.get("/")["Cache-Control"])

    def test_schema_authorized(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)

    def test_public_health_and_no_media_exposure(self):
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/private-media/test.pdf").status_code, 404)

    def test_language_preference_cookie(self):
        response = self.client.post("/i18n/setlang/", {"language": "ml", "next": "/"})
        self.assertEqual(response.cookies["django_language"].value, "ml")

    @override_settings(DEBUG=False)
    def test_friendly_errors_do_not_show_tracebacks(self):
        response = self.client.get("/missing/")
        self.assertContains(response, "couldn’t find", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_session_expiry_configured(self):
        from django.conf import settings

        self.assertEqual(settings.SESSION_COOKIE_AGE, 1800)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
