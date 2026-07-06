"""Tests for the abstract Worker base class."""

from django.test import SimpleTestCase, TestCase

from engine.processing.models import Worker
from engine.telegram.models import Bot, Job


class WorkerPollSelectRelatedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bot = Bot.objects.create(name="test-bot", telegram_api_token="tok")

    def test_poll_select_related_is_applied(self):
        Job.objects.create(
            bot=self.bot,
            reply_target="1",
            raw_input="hi",
        )

        class Sub(Worker):
            poll_filters = {"bot__name": self.bot.name}
            poll_select_related = ("bot",)

            def process(
                self, *, bot_id: int, raw_input: str
            ) -> tuple[str | None, str | None]:
                return "ok", None

        Sub().run()

        self.assertTrue(
            Job.objects.filter(processing_finished_at__isnull=False).exists()
        )

    def test_poll_without_filters_selects_any_ready_job(self):
        Job.objects.create(
            bot=self.bot,
            reply_target="1",
            raw_input="hi",
        )

        class Sub(Worker):
            poll_select_related = ("bot",)

            def process(
                self, *, bot_id: int, raw_input: str
            ) -> tuple[str | None, str | None]:
                return "ok", None

        Sub().run()

        self.assertTrue(
            Job.objects.filter(processing_finished_at__isnull=False).exists()
        )


class WorkerInitSubclassTests(SimpleTestCase):
    def test_allows_multiple_worker_subclasses(self):
        class _First(Worker):
            def process(
                self, *, bot_id: int, raw_input: str
            ) -> tuple[str | None, str | None]:
                return "first", None

        class _Second(Worker):
            def process(
                self, *, bot_id: int, raw_input: str
            ) -> tuple[str | None, str | None]:
                return "second", None

        self.assertEqual(_First().process(bot_id=1, raw_input=""), ("first", None))
        self.assertEqual(_Second().process(bot_id=1, raw_input=""), ("second", None))


class WorkerExtendedTests(TestCase):
    """Extended coverage for pk mode, error handling, and edge cases."""

    @classmethod
    def setUpTestData(cls):
        cls.bot = Bot.objects.create(name="ext-test-bot", telegram_api_token="tok")

    def test_run_returns_when_no_job_exists(self):
        class _Sub(Worker):
            def process(self, *, bot_id, raw_input):
                return "ok", None

        _Sub().run()

    def test_run_by_pk_processes_job(self):
        class _Sub(Worker):
            def process(self, *, bot_id, raw_input):
                return "result", None

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.raw_output, "result")

    def test_run_by_pk_missing_job_returns(self):
        class _Sub(Worker):
            def process(self, *, bot_id, raw_input):
                return "ok", None

        _Sub().run(job_pk=99999)
        self.assertFalse(Job.objects.exists())

    def test_run_by_pk_skips_already_processed_job(self):
        class _Sub(Worker):
            def process(self, *, bot_id, raw_input):
                return "overwritten", None

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        Job.objects.filter(pk=job.pk).update(
            raw_output="existing",
            processing_started_at="2024-01-01 00:00:00+00",
            processing_finished_at="2024-01-01 00:00:00+00",
        )
        _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.raw_output, "existing")

    def test_save_result_with_error(self):
        class _Sub(Worker):
            def process(self, *, bot_id, raw_input):
                return None, "handled error"

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.error, "handled error")
        self.assertIsNotNone(job.processing_finished_at)

    def test_run_raises_and_saves_error_when_process_fails(self):
        class _Sub(Worker):
            def process(self, *, bot_id, raw_input):
                raise RuntimeError("boom")

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        with self.assertRaises(RuntimeError):
            _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertIsNotNone(job.error)
        self.assertIsNotNone(job.processing_finished_at)

    def test_poll_without_select_related(self):
        class _Sub(Worker):
            poll_filters = {"bot__name": self.bot.name}

            def process(self, *, bot_id, raw_input):
                return "ok", None

        Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        _Sub().run()
        self.assertTrue(
            Job.objects.filter(processing_finished_at__isnull=False).exists()
        )
