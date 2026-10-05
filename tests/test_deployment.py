from pathlib import Path
from unittest.mock import patch

import yaml
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from apps.accounts.checks import storage_and_browser_checks
from apps.accounts.security import client_ip
from apps.common.middleware import TrustedProxyMiddleware


class ProxyTests(SimpleTestCase):
    @override_settings(TRUSTED_PROXY_CIDRS=["172.30.80.1/32"])
    def test_only_direct_trusted_proxy_can_supply_client_ip(self):
        factory = RequestFactory()
        trusted = factory.get("/", REMOTE_ADDR="172.30.80.1", HTTP_X_REAL_IP="203.0.113.8")
        self.assertEqual(client_ip(trusted), "203.0.113.8")
        other = factory.get("/", REMOTE_ADDR="192.0.2.1", HTTP_X_REAL_IP="203.0.113.8")
        self.assertEqual(client_ip(other), "192.0.2.1")
        trusted.META["HTTP_X_REAL_IP"] = "203.0.113.8, 192.0.2.4"
        self.assertEqual(client_ip(trusted), "172.30.80.1")

    @override_settings(TRUSTED_PROXY_CIDRS=["172.30.80.1/32"])
    def test_middleware_normalizes_once_and_discards_forwarded_chain(self):
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="172.30.80.1",
            HTTP_X_REAL_IP="203.0.113.8",
            HTTP_X_FORWARDED_FOR="fake",
        )
        TrustedProxyMiddleware(lambda r: HttpResponse())(request)
        self.assertEqual(request.META["REMOTE_ADDR"], "203.0.113.8")
        self.assertNotIn("HTTP_X_FORWARDED_FOR", request.META)
        self.assertNotIn("HTTP_X_REAL_IP", request.META)
        self.assertEqual(settings.REST_FRAMEWORK["NUM_PROXIES"], 0)

    @override_settings(TRUSTED_PROXY_CIDRS=["0.0.0.0/0"])
    def test_global_trust_rejected_by_deployment_check(self):
        self.assertIn("gmfms.E005", {error.id for error in storage_and_browser_checks(None)})


class ReadinessTests(TestCase):
    def test_ready_database(self):
        response = self.client.get("/internal/ready/")
        self.assertEqual(response.json(), {"status": "ready"})
        self.assertIn("no-store", response["Cache-Control"])

    def test_unavailable_database_does_not_expose_errors(self):
        with patch(
            "django.db.connection.cursor", side_effect=RuntimeError("private database password")
        ):
            response = self.client.get("/internal/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})


class DeploymentContractTests(SimpleTestCase):
    def test_compose_boundary_and_persistence(self):
        data = yaml.safe_load(
            (Path(settings.BASE_DIR) / "docker-compose.yml").read_text(encoding="utf-8")
        )
        web = data["services"]["web"]
        db = data["services"]["database"]
        self.assertEqual(web["ports"], ["127.0.0.1:18000:8000"])
        self.assertNotIn("ports", db)
        self.assertEqual(web["env_file"], "deploy/web.env")
        self.assertEqual(data["services"]["release"]["env_file"], "deploy/migration.env")
        self.assertIn("private_media:/data/private_media", web["volumes"])
        self.assertEqual(web["depends_on"]["database"]["condition"], "service_healthy")

    def test_context_excludes_secrets_and_existing_data(self):
        excludes = (
            (Path(settings.BASE_DIR) / ".dockerignore").read_text(encoding="utf-8").splitlines()
        )
        for value in [
            ".env",
            ".env.*",
            "private_media",
            "artifacts",
            "*.sqlite3*",
            "deploy/*.env",
            "backups",
        ]:
            self.assertIn(value, excludes)

    def test_proxy_has_no_public_media_alias_and_no_sensitive_access_log_fields(self):
        nginx = (Path(settings.BASE_DIR) / "deploy/nginx.conf.example").read_text(encoding="utf-8")
        log = next(line for line in nginx.splitlines() if line.startswith("log_format"))
        self.assertNotIn("$request_uri", log)
        self.assertNotIn("$http_referer", log)
        self.assertNotIn("alias ", nginx)
        self.assertIn("proxy_set_header X-Real-IP $remote_addr", nginx)
        self.assertIn("location /internal/ { return 404; }", nginx)
