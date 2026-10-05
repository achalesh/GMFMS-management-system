from .base import *  # noqa: F403

SECRET_KEY = "tests-only-not-for-deployment-573861c1b33e4c74a2655b47d04c036f"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"], "level": "CRITICAL"},
    "loggers": {
        name: {"handlers": ["null"], "propagate": False}
        for name in ["gmfms.audit", "gmfms.security", "django.request", "django.security"]
    },
}
