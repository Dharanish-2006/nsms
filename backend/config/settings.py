"""Django settings for the Rice Mill Monitor backend.

Everything environment specific comes from environment variables (or a local
.env file); see .env.example for the full list.
"""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # python-dotenv is optional
    pass


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "insecure-development-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY (or DJANGO_DEBUG=1 for local work).")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")

INSTALLED_APPS = [
    "daphne",  # ASGI server; must come before staticfiles so `runserver` is ASGI
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "corsheaders",
    "apps.accounts",
    "apps.plants",
    "apps.telemetry",
    "apps.alerts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# --- Database ---------------------------------------------------------------
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=env_int("DB_CONN_MAX_AGE", 0),
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Realtime and cache -----------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# --- Auth -------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTH_TOKEN_TTL_HOURS = env_int("AUTH_TOKEN_TTL_HOURS", 24 * 7)

# --- REST framework ---------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.BearerTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "apps.common.errors.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
    "NUM_PROXIES": env_int("NUM_PROXIES", 0) or None,
    "DEFAULT_THROTTLE_RATES": {
        "login": "20/min",
        "register": "10/hour",
        "otp": "30/hour",
    },
}

# --- Internationalisation ---------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"  # day and hour boundaries in reports are IST
USE_I18N = False
USE_TZ = True

# --- Static files (Django admin only) ---------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# --- CORS / security --------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

if env_bool("TRUST_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0)
    SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Email (OTP) ------------------------------------------------------------
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Rice Mill Monitor <no-reply@example.com>")

# --- SMS --------------------------------------------------------------------
SMS_BACKEND = os.environ.get("SMS_BACKEND", "console")  # console | sns
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

# --- Telemetry --------------------------------------------------------------
# A machine is "unknown" in the UI when silent for this long (matches the frontend).
STALE_AFTER_SEC = env_int("STALE_AFTER_SEC", 120)
# Largest gap between two samples that is still integrated into runtime / energy.
MAX_SAMPLE_GAP_SEC = env_int("MAX_SAMPLE_GAP_SEC", 300)
RAW_SAMPLE_INTERVAL_SEC = env_int("RAW_SAMPLE_INTERVAL_SEC", 15)
RAW_RETENTION_DAYS = env_int("RAW_RETENTION_DAYS", 7)
# Readings stamped further ahead than this are rejected (gateway clock wrong).
MAX_CLOCK_SKEW_SEC = env_int("MAX_CLOCK_SKEW_SEC", 300)
INGEST_MAX_READINGS = env_int("INGEST_MAX_READINGS", 500)

# --- Alerts -----------------------------------------------------------------
ALERT_SMS_COOLDOWN_MIN = env_int("ALERT_SMS_COOLDOWN_MIN", 30)
ALERT_SMS_ASYNC = True  # send SMS from a worker thread so ingestion never waits on SNS

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
