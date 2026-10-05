import secrets

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)
# Ephemeral fallback is development-only. Persist a local key for stable sessions.
SECRET_KEY = env("SECRET_KEY", default="") or secrets.token_urlsafe(64)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
