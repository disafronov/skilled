from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "settings.py"


def load_settings_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SETTINGS_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load settings module")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_env_bool_uses_default_for_empty_values(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG", "")

    module = load_settings_module("config._settings_empty_bool_test")

    assert module.DEBUG is True


def test_secure_ssl_redirect_exempts_health_paths(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG", "1")
    monkeypatch.setenv("DJANGO_SECURE_SSL_REDIRECT", "true")

    module = load_settings_module("config._settings_secure_redirect_test")

    assert module.SECURE_SSL_REDIRECT is True
    assert module.SECURE_REDIRECT_EXEMPT == [r"^health/"]


def test_secure_flags_can_be_disabled_with_false_strings(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG", "0")
    monkeypatch.setenv("DJANGO_SECURE_SSL_REDIRECT", "false")
    monkeypatch.setenv("DJANGO_SESSION_COOKIE_SECURE", "0")
    monkeypatch.setenv("DJANGO_CSRF_COOKIE_SECURE", "off")

    module = load_settings_module("config._settings_secure_false_test")

    assert module.SECURE_SSL_REDIRECT is False
    assert module.SESSION_COOKIE_SECURE is False
    assert module.CSRF_COOKIE_SECURE is False
    assert not hasattr(module, "SECURE_REDIRECT_EXEMPT")


def test_insecure_secret_key_in_production_raises_error(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG", "False")
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)

    import pytest

    with pytest.raises(RuntimeError, match="DJANGO_SECRET_KEY must be set"):
        load_settings_module("config._settings_insecure_secret_test")
