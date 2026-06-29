import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from apps.common.fields import EncryptedCharField, _cipher


@pytest.fixture(autouse=True)
def _clear_cipher_cache():
    """Prevent cache pollution across tests that set FIELD_ENCRYPTION_KEY."""
    _cipher.cache_clear()
    yield
    _cipher.cache_clear()


def test_get_prep_value_none():
    field = EncryptedCharField()
    assert field.get_prep_value(None) is None


def test_from_db_value_none():
    field = EncryptedCharField()
    assert field.from_db_value(None, None, None) is None


def test_to_python_none():
    field = EncryptedCharField()
    assert field.to_python(None) is None


def test_from_db_value_corrupt(caplog):
    field = EncryptedCharField()
    assert field.from_db_value("not-encrypted", None, None) is None
    assert "Unable to decrypt encrypted field value" in caplog.text


def test_to_python_corrupt(caplog):
    field = EncryptedCharField()
    assert field.to_python("not-encrypted") == "not-encrypted"
    assert "Unable to decrypt encrypted field value" in caplog.text


def test_roundtrip():
    field = EncryptedCharField()
    value = "secret-token-123"
    encrypted = field.get_prep_value(value)
    decrypted = field.from_db_value(encrypted, None, None)
    assert decrypted == value
    assert encrypted != value


def test_plaintext_migration(caplog):
    field = EncryptedCharField()
    result = field.from_db_value("old-plaintext-token", None, None)
    assert result is None
    assert "Unable to decrypt encrypted field value" in caplog.text


def test_field_encryption_key_roundtrip():
    key = Fernet.generate_key().decode()
    with patch.dict(os.environ, {"FIELD_ENCRYPTION_KEY": key}):
        _cipher.cache_clear()
        field = EncryptedCharField()
        value = "my-secret-token"
        encrypted = field.get_prep_value(value)
        decrypted = field.from_db_value(encrypted, None, None)
        assert decrypted == value


def test_cipher_raises_without_encryption_key():
    with patch.dict(os.environ):
        os.environ.pop("FIELD_ENCRYPTION_KEY", None)
        _cipher.cache_clear()
        with pytest.raises(RuntimeError, match="FIELD_ENCRYPTION_KEY is not set"):
            _cipher()


def test_field_encryption_key_change_makes_old_data_unreadable():
    key1 = Fernet.generate_key().decode()
    with patch.dict(os.environ, {"FIELD_ENCRYPTION_KEY": key1}):
        _cipher.cache_clear()
        field = EncryptedCharField()
        encrypted = field.get_prep_value("old-secret")

    key2 = Fernet.generate_key().decode()
    with patch.dict(os.environ, {"FIELD_ENCRYPTION_KEY": key2}):
        _cipher.cache_clear()
        result = field.from_db_value(encrypted, None, None)
        assert result is None
