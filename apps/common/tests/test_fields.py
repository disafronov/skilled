from apps.common.fields import EncryptedCharField


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
    assert field.from_db_value("not-encrypted", None, None) == "not-encrypted"
    assert "Unable to decrypt encrypted field value — keeping raw" in caplog.text


def test_to_python_corrupt(caplog):
    field = EncryptedCharField()
    assert field.to_python("not-encrypted") == "not-encrypted"
    assert "Unable to decrypt encrypted field value — keeping raw" in caplog.text


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
    assert result == "old-plaintext-token"
    assert "Unable to decrypt encrypted field value — keeping raw" in caplog.text
