import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    """Parse an env var as a boolean (truthy: 1, true, yes, on)."""
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


_insecure_key = "insecure-dev-key-change-in-production"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", _insecure_key)
DEBUG = env_bool("DJANGO_DEBUG", True)

if not DEBUG and SECRET_KEY == _insecure_key:
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a strong, unique value in production"
    )
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
BASE_URL = os.getenv("DJANGO_BASE_URL", "").rstrip("/")
WEBHOOK_COOLDOWN_SECONDS = int(os.getenv("WEBHOOK_COOLDOWN_SECONDS", "300"))
WEBHOOK_FALLBACK_PENDING_THRESHOLD = int(
    os.getenv("WEBHOOK_FALLBACK_PENDING_THRESHOLD", "5")
)
TELEGRAM_ACK_REACTION = os.getenv("TELEGRAM_ACK_REACTION", "🤔")
TELEGRAM_INTAKE_DEBOUNCE_SECONDS = int(
    os.getenv("TELEGRAM_INTAKE_DEBOUNCE_SECONDS", "10")
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.library",
    "apps.inference",
    "engine.telegram",
    "engine.workers",
    "apps.llm",
    "apps.ops",
    "django_q",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEST_RUNNER = "config.tests.runner.PytestTestRunner"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.getenv("DATABASE_HOST", "localhost"),
        "PORT": os.getenv("DATABASE_PORT", "5432"),
        "NAME": os.getenv("DATABASE_NAME", "database"),
        "USER": os.getenv("DATABASE_USER", "user"),
        "PASSWORD": os.getenv("DATABASE_PASSWORD", "password"),
    }
}

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django Q2 — PostgreSQL as task broker
Q_CLUSTER = {
    "name": os.getenv("Q_CLUSTER_NAME", "skilled"),
    "workers": int(os.getenv("Q_WORKERS", 2)),
    "timeout": int(os.getenv("Q_TIMEOUT", 600)),
    "retry": int(os.getenv("Q_RETRY", 660)),
    "queue_limit": int(os.getenv("Q_QUEUE_LIMIT", 50)),
    "bulk": int(os.getenv("Q_BULK", 10)),
    "orm": "default",
    "catch_up": False,
}

# Worker function path for Django Q2 tasks
Q2_WORKER_FUNC = "apps.llm.tasks.worker"

# django-q2 success task retention (seconds, default 24h)
Q2_SUCCESS_RETENTION_SECONDS = 86400

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Logging — console output for app-level loggers
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "mask_bot_token": {
            "()": "engine.common.log_filters.BotTokenFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["mask_bot_token"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "workers": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
        },
    },
}

# Security
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", not DEBUG)
CSRF_TRUSTED_ORIGINS = os.getenv(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://127.0.0.1,http://localhost"
).split(",")
if SECURE_SSL_REDIRECT:
    SECURE_REDIRECT_EXEMPT = [r"^health/"]
