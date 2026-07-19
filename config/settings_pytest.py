"""
Pytest settings module.

Pytest should use a single, explicit settings module so test-only overrides do
not leak into runtime settings and Django's default test runner is not a second
execution path.
"""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESSIV

# Force a test encryption key early — before any EncryptedCharField access.
# os.environ.setdefault is insufficient because `make test` sources env.example
# which may contain FIELD_ENCRYPTION_KEY= (empty string), preventing the
# default from being set.  Under pytest-xdist, workers that inherit an empty
# FIELD_ENCRYPTION_KEY would then raise RuntimeError in _cipher().
os.environ["FIELD_ENCRYPTION_KEY"] = AESSIV.generate_key(256).hex()

from .settings import *  # noqa: F401,F403,E402

DEBUG = True  # Keep verbose test logging regardless of production-safe default.

STORAGES = dict(STORAGES)  # noqa: F405
STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

MIDDLEWARE = [  # noqa: F405
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]

ALLOWED_HOSTS = [host for host in ALLOWED_HOSTS if host]  # noqa: F405
BASE_URL = ""  # noqa: F405
CSRF_TRUSTED_ORIGINS = [  # noqa: F405
    origin for origin in CSRF_TRUSTED_ORIGINS if origin  # noqa: F405
]

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
