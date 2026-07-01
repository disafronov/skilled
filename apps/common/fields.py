"""Deterministic encrypted CharField using AES-SIV."""

import base64
import logging
import os
from functools import cache
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from django.db import models

logger = logging.getLogger(__name__)


@cache
def _cipher() -> AESSIV:
    """Return a cached AES-SIV cipher initialised from FIELD_ENCRYPTION_KEY."""
    raw = os.environ.get("FIELD_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. "
            "Generate one with: "
            'python -c "import secrets; print(secrets.token_bytes(32).hex())"'
        )
    key = bytes.fromhex(raw)
    if len(key) not in (16, 24, 32):
        raise RuntimeError(
            f"FIELD_ENCRYPTION_KEY decodes to {len(key)} bytes — "
            "AES-SIV requires 16, 24, or 32 bytes "
            "(128, 192, or 256 bits)."
        )
    return AESSIV(key)


class EncryptedCharField(models.CharField):
    """CharField with deterministic AES-SIV encryption at rest.

    Same plaintext always produces the same ciphertext, enabling
    database-level lookups (e.g. ``Bot.objects.filter(token=...)``).
    """

    def get_prep_value(self, value: Any) -> str | None:
        # Skip CharField.get_prep_value → it calls to_python which would
        # try to decrypt plaintext input. We encrypt directly here.
        if value is None:
            return None
        value = str(value)
        return base64.b64encode(_cipher().encrypt(value.encode(), [])).decode()

    def from_db_value(
        self,
        value: str | None,
        _expression: Any,
        connection: Any,
    ) -> str | None:
        if value is None:
            return None
        try:
            return _cipher().decrypt(base64.b64decode(value), []).decode()
        except (InvalidTag, Exception) as exc:
            # Broad except: base64 decode errors, wrong key, corrupted data.
            if isinstance(exc, InvalidTag):
                logger.error(
                    "Unable to decrypt encrypted field value (auth failure) "
                    "— returning None: %s",
                    value[:16],
                )
            else:
                logger.error(
                    "Unable to decrypt encrypted field value (%s) "
                    "— returning None: %s",
                    type(exc).__name__,
                    value[:16],
                )
            # Return None rather than leaking the encrypted blob
            # (which could be sent to external APIs as a credential).
            return None

    def to_python(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value)
        try:
            return _cipher().decrypt(base64.b64decode(raw), []).decode()
        except InvalidTag, Exception:
            # `from_db_value` handles DB-stored values (encrypted blobs);
            # `to_python` is also called during deserialisation (loaddata/
            # fixtures), where returning raw could double-encrypt on save
            # or leak ciphertext. Return None to stay safe and consistent
            # with `from_db_value`.
            logger.warning("Unable to decrypt encrypted field value — returning None")
            return None
