"""Explicit PostgreSQL test database only; never point at a live database."""

from django.core.exceptions import ImproperlyConfigured

from .base import env
from .test import *  # noqa: F403

url = env("TEST_DATABASE_URL", default="")
if not url:
    raise ImproperlyConfigured("Set TEST_DATABASE_URL for a disposable PostgreSQL test database.")
DATABASES = {"default": env.db_url_config(url)}
if not DATABASES["default"]["ENGINE"].endswith("postgresql"):
    raise ImproperlyConfigured("Integration tests require PostgreSQL.")
DATABASES["default"]["TEST"] = {"NAME": "test_gmfms_integration"}
