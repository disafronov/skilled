import base64
import hashlib
import logging
import os
from functools import cache
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.signing import BadSignature, Signer
from django.db import models

_OLD_SIGNER = Signer(salt="skilled.encrypted_field")
logger = logging.getLogger(__name__)


@cache
def _cipher() -> Fernet:
    raw = os.environ.get("FIELD_ENCRYPTION_KEY")
    if raw:
        return Fernet(raw)
    # Backward-compatible fallback: derive from SECRET_KEY
    derived: bytes = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(derived)


class EncryptedCharField(models.CharField):
    def get_prep_value(self, value: Any) -> str | None:
        value = super().get_prep_value(value)
        if value is None:
            return None
        return _cipher().encrypt(value.encode()).decode()

    def from_db_value(
        self,
        value: str | None,
        _expression: Any,
        connection: Any,
    ) -> str | None:
        if value is None:
            return None
        try:
            return _cipher().decrypt(value.encode()).decode()
        except InvalidToken:
            pass
        try:
            return cast(str, _OLD_SIGNER.unsign_object(value))
        except BadSignature:
            logger.error(
                "Unable to decrypt encrypted field value — returning None: %s",
                value[:16],
            )
            # Both Fernet and Signer failed — return None rather than leaking
            # the encrypted blob (which could be sent to external APIs as a
            # credential).
            return None

    def to_python(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value)
        try:
            return _cipher().decrypt(raw.encode()).decode()
        except InvalidToken:
            pass
        try:
            return cast(str, _OLD_SIGNER.unsign_object(raw))
        except BadSignature:
            # `from_db_value` handles DB-stored values (must be encrypted);
            # `to_python` also receives plaintext user input — pass it through.
            logger.warning("Unable to decrypt encrypted field value — keeping raw")
            return raw
