from subprocess import TimeoutExpired
from unittest.mock import MagicMock, patch

from django.test import TestCase


class ManagementCommandTests(TestCase):
    @patch("apps.jobs.management.commands.llm_worker_once.llm_worker")
    def test_llm_worker_once_calls_task(self, task):
        from apps.jobs.management.commands.llm_worker_once import Command

        Command().handle()

        task.assert_called_once_with()

    @patch("apps.jobs.management.commands.telegram_ingest_once.telegram_ingest")
    def test_telegram_ingest_once_calls_task(self, task):
        from apps.jobs.management.commands.telegram_ingest_once import Command

        Command().handle()

        task.assert_called_once_with()

    @patch("apps.jobs.management.commands.telegram_deliver_once.telegram_deliver")
    def test_telegram_deliver_once_calls_task(self, task):
        from apps.jobs.management.commands.telegram_deliver_once import Command

        Command().handle()

        task.assert_called_once_with()

    @patch("apps.jobs.management.commands.dev._supervise")
    @patch("apps.jobs.management.commands.dev.subprocess.Popen")
    def test_dev_command_supervises_qcluster_and_runserver(self, popen, supervise):
        from apps.jobs.management.commands.dev import Command

        first = MagicMock()
        second = MagicMock()
        popen.side_effect = [first, second]

        Command().handle()

        self.assertEqual(popen.call_count, 2)
        self.assertEqual(popen.call_args_list[0].args[0][1:], ["manage.py", "qcluster"])
        self.assertEqual(
            popen.call_args_list[1].args[0][1:],
            ["manage.py", "runserver", "0.0.0.0:8000"],
        )
        supervise.assert_called_once_with([first, second])

    @patch("apps.jobs.management.commands.start._supervise")
    @patch("apps.jobs.management.commands.start.subprocess.Popen")
    def test_start_command_supervises_qcluster_and_gunicorn(self, popen, supervise):
        from apps.jobs.management.commands.start import Command

        first = MagicMock()
        second = MagicMock()
        popen.side_effect = [first, second]

        Command().handle()

        self.assertEqual(popen.call_count, 2)
        self.assertEqual(popen.call_args_list[0].args[0][1:], ["manage.py", "qcluster"])
        self.assertEqual(popen.call_args_list[1].args[0], ["gunicorn", "config.wsgi"])
        supervise.assert_called_once_with([first, second])


class SupervisorTests(TestCase):
    def test_stop_terminates_all_and_kills_timeout_survivor(self):
        from apps.jobs.management import supervisor

        first = MagicMock()
        second = MagicMock()
        second.wait.side_effect = TimeoutExpired(cmd="child", timeout=1)

        supervisor._stop([first, second])

        first.terminate.assert_called_once_with()
        second.terminate.assert_called_once_with()
        first.wait.assert_called_once()
        second.wait.assert_called_once()
        second.kill.assert_called_once_with()

    @patch("apps.jobs.management.supervisor.time.sleep", side_effect=AssertionError)
    @patch("apps.jobs.management.supervisor._stop")
    @patch("apps.jobs.management.supervisor.signal.signal")
    def test_supervise_exits_with_child_return_code(self, signal_fn, stop, sleep):
        from apps.jobs.management import supervisor

        first = MagicMock()
        second = MagicMock()
        first.poll.return_value = None
        second.poll.return_value = 7

        with self.assertRaises(SystemExit) as exc:
            supervisor._supervise([first, second])

        self.assertEqual(exc.exception.code, 7)
        stop.assert_called_once_with([first])

    @patch("apps.jobs.management.supervisor.sys.exit", side_effect=SystemExit(0))
    @patch("apps.jobs.management.supervisor._stop")
    @patch("apps.jobs.management.supervisor.signal.signal")
    def test_supervise_sigterm_handler_stops_and_exits_zero(
        self,
        signal_fn,
        stop,
        exit_mock,
    ):
        from apps.jobs.management import supervisor

        signal_fn.side_effect = SystemExit("handlers registered")

        with self.assertRaises(SystemExit):
            supervisor._supervise([])

        sigterm_handler = signal_fn.call_args_list[0].args[1]
        with self.assertRaises(SystemExit):
            sigterm_handler(15, None)

        stop.assert_called_once_with([])
        exit_mock.assert_called_once_with(0)

    @patch("apps.jobs.management.supervisor.time.sleep", side_effect=SystemExit)
    @patch("apps.jobs.management.supervisor.signal.raise_signal")
    @patch("apps.jobs.management.supervisor._stop")
    @patch("apps.jobs.management.supervisor.signal.signal")
    def test_supervise_sigint_handler_stops_and_reraises_signal(
        self,
        signal_fn,
        stop,
        raise_signal,
        sleep,
    ):
        from apps.jobs.management import supervisor

        with self.assertRaises(SystemExit):
            supervisor._supervise([])

        sigint_handler = signal_fn.call_args_list[1].args[1]
        sigint_handler(2, None)

        stop.assert_called_once_with([])
        self.assertEqual(signal_fn.call_args_list[2].args[0], 2)
        raise_signal.assert_called_once_with(2)
