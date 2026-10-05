from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parents[2]
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

INSTALLED_APPS = [
    "apps.accounts.apps.AccountsConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "axes",
    "apps.organization",
    "apps.audit",
    "apps.dashboard",
    "apps.reports",
    "apps.locations",
    "apps.registrations",
    "apps.facilitators",
    "apps.verification",
    "apps.idcards",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middleware.BrowserSecurityMiddleware",
    "apps.common.middleware.TrustedProxyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.PrivateResponseMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.organization.context_processors.branding",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
DATABASES["default"]["CONN_MAX_AGE"] = 60
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    DATABASES["default"]["OPTIONS"] = {"timeout": 20}
elif DATABASES["default"]["ENGINE"].endswith("mysql"):
    DATABASES["default"]["OPTIONS"] = {
        "charset": "utf8mb4",
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    }

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "apps.accounts.validators.RepeatedPatternValidator"},
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=1800)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
PASSWORD_RESET_TIMEOUT = 3600
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(minutes=env.int("AXES_COOLOFF_MINUTES", default=15))
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "errors/429.html"
AXES_HTTP_RESPONSE_CODE = 429
AXES_ENABLE_ACCESS_FAILURE_LOG = False
AXES_CLIENT_IP_CALLABLE = "apps.accounts.security.client_ip"

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ml", "മലയാളം")]
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / env("STATIC_ROOT", default="staticfiles")
STATICFILES_DIRS = [BASE_DIR / "static"]
# Deliberately never served by urls.py; future downloads need authorization.
MEDIA_ROOT = BASE_DIR / env("MEDIA_ROOT", default="private_media")
MEDIA_URL = "/private-media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://127.0.0.1:8000").rstrip("/")
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
REST_FRAMEWORK = {
    "NUM_PROXIES": 0,
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/hour", "user": "1000/hour"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SPECTACULAR_SETTINGS = {
    "TITLE": "GMFMS administration API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["apps.accounts.permissions.HasDashboardAccess"],
    "SERVE_AUTHENTICATION": ["rest_framework.authentication.SessionAuthentication"],
}
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.invalid")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "gmfms.application": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "gmfms.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "gmfms.audit": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "axes": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

FILE_UPLOAD_HANDLERS = [
    "apps.registrations.upload_handlers.RegistrationUploadLimitHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
DATA_UPLOAD_MAX_NUMBER_FILES = 9
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700

# Malformed PDF diagnostics may include source fragments; do not log applicant document content.
LOGGING["handlers"]["discard_pdf_diagnostics"] = {"class": "logging.NullHandler"}
LOGGING["loggers"]["pypdf"] = {"handlers": ["discard_pdf_diagnostics"], "propagate": False}

# Suppress bearer-like verification tokens in Django request/server log messages.
LOGGING.setdefault("filters", {})["verification_redaction"] = {
    "()": "apps.verification.logging.RedactVerificationToken"
}
LOGGING["handlers"]["console"]["filters"] = ["verification_redaction"]
LOGGING["loggers"]["django.server"] = {"handlers": ["console"], "level": "INFO", "propagate": False}
LOGGING["loggers"]["django.request"] = {
    "handlers": ["console"],
    "level": "WARNING",
    "propagate": False,
}

ID_CARD_FONT_PATH = env("ID_CARD_FONT_PATH", default="")

TRUSTED_PROXY_CIDRS = env.list("TRUSTED_PROXY_CIDRS", default=[])
