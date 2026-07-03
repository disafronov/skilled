"""Tests for ops management commands and supervisor."""

import sys
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

from django.test import TestCase


class ManagementCommandTests(TestCase):
    @patch("apps.ops.management.commands.dev._supervise")
    @patch("apps.ops.management.commands.dev._spawn")
    def test_dev_command_supervises_qcluster_and_runserver(self, spawn, supervise):
        from apps.ops.management.commands.dev import Command

        first = MagicMock()
        second = MagicMock()
        spawn.side_effect = [first, second]

        Command().handle()

        self.assertEqual(spawn.call_count, 2)
        self.assertEqual(
            spawn.call_args_list[0][0],
            (sys.executable, "manage.py", "qcluster"),
        )
        self.assertEqual(
            spawn.call_args_list[1][0],
            (sys.executable, "manage.py", "runserver", "0.0.0.0:8000"),
        )
        supervise.assert_called_once_with([first, second])

    @patch("apps.ops.management.commands.start._supervise")
    @patch("apps.ops.management.commands.start._spawn")
    def test_start_command_supervises_qcluster_and_gunicorn(self, spawn, supervise):
        from apps.ops.management.commands.start import Command

        first = MagicMock()
        second = MagicMock()
        spawn.side_effect = [first, second]

        Command().handle()

        self.assertEqual(spawn.call_count, 2)
        self.assertEqual(
            spawn.call_args_list[0][0],
            (sys.executable, "manage.py", "qcluster"),
        )
        self.assertEqual(
            spawn.call_args_list[1][0],
            ("gunicorn", "config.wsgi"),
        )
        supervise.assert_called_once_with([first, second])


class SupervisorTests(TestCase):
    @patch("apps.ops.management.supervisor.subprocess.Popen")
    def test_spawn_starts_process_with_fixed_args_and_cwd(self, popen):
        from django.conf import settings

        from apps.ops.management import supervisor

        proc = supervisor._spawn(sys.executable, "manage.py", "qcluster")

        popen.assert_called_once_with(
            [sys.executable, "manage.py", "qcluster"],
            cwd=settings.BASE_DIR,
        )
        self.assertIs(proc, popen.return_value)

    def test_stop_terminates_all_and_kills_timeout_survivor(self):
        from apps.ops.management import supervisor

        first = MagicMock()
        second = MagicMock()
        second.wait.side_effect = TimeoutExpired(cmd="child", timeout=1)

        supervisor._stop([first, second])

        first.terminate.assert_called_once_with()
        second.terminate.assert_called_once_with()
        first.wait.assert_called_once()
        second.wait.assert_called_once()
        second.kill.assert_called_once_with()

    @patch("apps.ops.management.supervisor.time.sleep", side_effect=AssertionError)
    @patch("apps.ops.management.supervisor._stop")
    @patch("apps.ops.management.supervisor.signal.signal")
    def test_supervise_exits_with_child_return_code(self, signal_fn, stop, sleep):
        from apps.ops.management import supervisor

        first = MagicMock()
        second = MagicMock()
        first.poll.return_value = None
        second.poll.return_value = 7

        with self.assertRaises(SystemExit) as exc:
            supervisor._supervise([first, second])

        self.assertEqual(exc.exception.code, 7)
        stop.assert_called_once_with([first])

    @patch("apps.ops.management.supervisor.sys.exit", side_effect=SystemExit(0))
    @patch("apps.ops.management.supervisor._stop")
    @patch("apps.ops.management.supervisor.signal.signal")
    def test_supervise_sigterm_handler_stops_and_exits_zero(
        self,
        signal_fn,
        stop,
        exit_mock,
    ):
        from apps.ops.management import supervisor

        signal_fn.side_effect = SystemExit("handlers registered")

        with self.assertRaises(SystemExit):
            supervisor._supervise([])

        sigterm_handler = signal_fn.call_args_list[0].args[1]
        with self.assertRaises(SystemExit):
            sigterm_handler(15, None)

        stop.assert_called_once_with([])
        exit_mock.assert_called_once_with(0)

    @patch("apps.ops.management.supervisor.time.sleep", side_effect=SystemExit)
    @patch("apps.ops.management.supervisor.signal.raise_signal")
    @patch("apps.ops.management.supervisor._stop")
    @patch("apps.ops.management.supervisor.signal.signal")
    def test_supervise_sigint_handler_stops_and_reraises_signal(
        self,
        signal_fn,
        stop,
        raise_signal,
        sleep,
    ):
        from apps.ops.management import supervisor

        with self.assertRaises(SystemExit):
            supervisor._supervise([])

        sigint_handler = signal_fn.call_args_list[1].args[1]
        sigint_handler(2, None)

        stop.assert_called_once_with([])
        self.assertEqual(signal_fn.call_args_list[2].args[0], 2)
        raise_signal.assert_called_once_with(2)
