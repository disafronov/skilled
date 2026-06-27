from typing import Any, cast

from django.core.signing import BadSignature, Signer
from django.db import models

_SIGNER = Signer(salt="skilled.encrypted_field")


class EncryptedCharField(models.CharField):
    def get_prep_value(self, value: Any) -> str | None:
        value = super().get_prep_value(value)
        if value is None:
            return None
        return _SIGNER.sign_object(value, compress=True)

    def from_db_value(
        self,
        value: str | None,
        _expression: Any,
        connection: Any,
    ) -> str | None:
        if value is None:
            return None
        try:
            return cast(str, _SIGNER.unsign_object(value))
        except BadSignature:
            return value

    def to_python(self, value: Any) -> str | None:
        if value is None:
            return None
        raw = str(value)
        try:
            return cast(str, _SIGNER.unsign_object(raw))
        except BadSignature:
            return raw
