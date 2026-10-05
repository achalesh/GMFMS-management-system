import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class ProductionConfigurationTests(SimpleTestCase):
    def configuration(self, **overrides):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "config.settings.production",
                "SECRET_KEY": "test-configuration-only-7afa9476566d4b54b37623c8ab92fe1fc1babc12",
                "ALLOWED_HOSTS": "media.example.org",
                "PUBLIC_BASE_URL": "https://media.example.org",
                "DATABASE_URL": "postgres://example:example@localhost:5432/example",
            }
        )
        environment.update(overrides)
        return subprocess.run(
            [
                sys.executable,
                "-c",
                "from config.settings import production as s; "
                "assert not s.DEBUG; assert s.SESSION_COOKIE_SECURE; "
                "assert s.CSRF_COOKIE_SECURE; assert s.SECURE_SSL_REDIRECT; "
                "assert s.SECURE_HSTS_SECONDS > 0; print('valid')",
            ],
            env=environment,
            cwd=Path(settings.BASE_DIR),
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_secure_production_defaults(self):
        result = self.configuration(DEBUG="True")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("valid", result.stdout)

    def test_production_rejects_unsafe_configuration(self):
        for values in [
            {"SECRET_KEY": "short"},
            {"ALLOWED_HOSTS": "*"},
            {"ALLOWED_HOSTS": ""},
            {"DATABASE_URL": "sqlite:///db.sqlite3"},
            {"PUBLIC_BASE_URL": "http://media.example.org"},
            {"PUBLIC_BASE_URL": "https://"},
            {"PUBLIC_BASE_URL": "https://user:pass@media.example.org"},
            {"PUBLIC_BASE_URL": "https://media.example.org/path"},
            {"PUBLIC_BASE_URL": "https://media.example.org/?token=value"},
            {"PUBLIC_BASE_URL": "https://media.example.org/#fragment"},
            {"PUBLIC_BASE_URL": "https://media.example.org:bad"},
            {"SESSION_COOKIE_AGE": "0"},
            {"SESSION_COOKIE_AGE": "90000"},
        ]:
            with self.subTest(values=values):
                self.assertNotEqual(self.configuration(**values).returncode, 0)
