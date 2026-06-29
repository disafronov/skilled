import logging
import os
from functools import cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from django.db import models

logger = logging.getLogger(__name__)


@cache
def _cipher() -> Fernet:
    raw = os.environ.get("FIELD_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. "
            "Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(raw)


class EncryptedCharField(models.CharField):
    def get_prep_value(self, value: Any) -> str | None:
        # Skip CharField.get_prep_value → it calls to_python which would
        # try to decrypt plaintext input. We encrypt directly here.
        if value is None:
            return None
        value = str(value)
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
            logger.error(
                "Unable to decrypt encrypted field value — returning None: %s",
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
            return _cipher().decrypt(raw.encode()).decode()
        except InvalidToken:
            # `from_db_value` handles DB-stored values (encrypted blobs);
            # `to_python` is also called during deserialisation (loaddata/
            # fixtures), where returning raw could double-encrypt on save
            # or leak ciphertext. Return None to stay safe and consistent
            # with `from_db_value`.
            logger.warning("Unable to decrypt encrypted field value — returning None")
            return None
