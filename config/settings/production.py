from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES, PUBLIC_BASE_URL, SESSION_COOKIE_AGE, env

DEBUG = False
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Production requires a unique SECRET_KEY of at least 50 characters.")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production requires explicit ALLOWED_HOSTS.")
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    raise ImproperlyConfigured("Production requires PostgreSQL or MySQL/MariaDB.")
origin = urlparse(PUBLIC_BASE_URL)
try:
    valid_port = origin.port is None or 1 <= origin.port <= 65535
except ValueError:
    valid_port = False
if (
    origin.scheme != "https"
    or not origin.hostname
    or origin.username
    or origin.password
    or origin.path not in ("", "/")
    or origin.query
    or origin.fragment
    or not valid_port
):
    raise ImproperlyConfigured(
        "PUBLIC_BASE_URL must be an absolute HTTPS origin without credentials, path, query or fragment."
    )
if not 60 <= SESSION_COOKIE_AGE <= 86400:
    raise ImproperlyConfigured("SESSION_COOKIE_AGE must be between 60 and 86400 seconds.")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
if env.bool("TRUST_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
