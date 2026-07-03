"""Tests for the task proxy module."""

from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from engine.proxy import worker


class ProxyWorkerTest(SimpleTestCase):
    @override_settings(Q2_WORKER_FUNC="engine.proxy.worker")
    def test_proxy_delegates_to_configured_func(self) -> None:
        called = []

        def fake(arg):
            called.append(arg)
            return "result"

        with patch("engine.proxy.worker.import_string", return_value=fake):
            result = worker("input")

        assert called == ["input"]
        assert result == "result"

    @override_settings(Q2_WORKER_FUNC="")
    def test_proxy_echoes_first_arg_when_unconfigured(self) -> None:
        result = worker("echo-this")
        assert result == "echo-this"

    @override_settings(Q2_WORKER_FUNC="")
    def test_proxy_returns_none_when_no_args_and_unconfigured(self) -> None:
        result = worker()
        assert result is None
