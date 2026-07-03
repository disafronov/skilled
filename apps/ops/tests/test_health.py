from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from django.db import DatabaseError
from django.test import Client, RequestFactory, override_settings

from apps.ops import health


def test_check_database_ok(monkeypatch) -> None:
    cursor = MagicMock()
    cursor.execute.return_value = None
    cursor_cm = MagicMock()
    cursor_cm.__enter__.return_value = cursor
    cursor_cm.__exit__.return_value = None

    monkeypatch.setattr(health.connection, "cursor", lambda: cursor_cm)

    ok, message = health.check_database()
    assert ok is True
    assert message == "Database connection OK"
    cursor.execute.assert_called_once_with("SELECT 1")


def test_check_database_error(monkeypatch) -> None:
    cursor_cm = MagicMock()
    cursor_cm.__enter__.side_effect = DatabaseError("boom")

    monkeypatch.setattr(health.connection, "cursor", lambda: cursor_cm)

    ok, message = health.check_database()
    assert ok is False
    assert message == "Database connection failed"


def test_readiness_returns_503_when_database_fails(monkeypatch) -> None:
    monkeypatch.setattr(health, "check_database", lambda: (False, "db down"))

    rf = RequestFactory()
    request = rf.get("/health/readiness/")

    response = health.readiness(request)
    assert response.status_code == 503
    assert json.loads(response.content) == {
        "status": "error",
        "checks": {"database": "db down"},
    }


@pytest.mark.parametrize(
    ("view", "expected_json"),
    [
        (health.liveness, {"status": "ok"}),
        (
            lambda request: health.readiness(request),
            {"status": "ok", "checks": {"database": "Database connection OK"}},
        ),
    ],
)
def test_health_views_return_ok_json(monkeypatch, view, expected_json) -> None:
    monkeypatch.setattr(
        health, "check_database", lambda: (True, "Database connection OK")
    )

    rf = RequestFactory()
    request = rf.get("/health/")

    response = view(request)
    assert response.status_code == 200
    assert json.loads(response.content) == expected_json


def test_health_probe_urls_keep_trailing_slash_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        health, "check_database", lambda: (True, "Database connection OK")
    )

    client = Client()

    for path in (
        "/health/liveness/",
        "/health/readiness/",
    ):
        assert client.get(path).status_code == 200


@override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=[r"^health/"])
def test_health_urls_are_exempt_from_ssl_redirect(monkeypatch) -> None:
    monkeypatch.setattr(
        health, "check_database", lambda: (True, "Database connection OK")
    )

    client = Client()

    for path in (
        "/health/liveness/",
        "/health/readiness/",
    ):
        assert client.get(path).status_code == 200
