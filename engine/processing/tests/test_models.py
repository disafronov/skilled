"""Tests for the abstract Worker base class."""

from django.test import TestCase

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

        Worker._testing_reset_subclass()

        class Sub(Worker):
            poll_filters = {"bot__name": self.bot.name}
            poll_select_related = ("bot",)

            def process(self, job: Job) -> tuple[str | None, str | None]:
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

        Worker._testing_reset_subclass()

        class Sub(Worker):
            poll_select_related = ("bot",)

            def process(self, job: Job) -> tuple[str | None, str | None]:
                return "ok", None

        Sub().run()

        self.assertTrue(
            Job.objects.filter(processing_finished_at__isnull=False).exists()
        )


class WorkerInitSubclassTests(TestCase):
    def test_cannot_subclass_worker_twice(self):
        Worker._testing_reset_subclass()

        class _First(Worker):
            def process(self, job: Job) -> tuple[str | None, str | None]:
                return "ok", None

        with self.assertRaises(TypeError):

            class _Second(Worker):  # type: ignore[no-redef]
                def process(self, job: Job) -> tuple[str | None, str | None]:
                    return "ok", None


class WorkerExtendedTests(TestCase):
    """Extended coverage for pk mode, error handling, and edge cases."""

    @classmethod
    def setUpTestData(cls):
        cls.bot = Bot.objects.create(name="ext-test-bot", telegram_api_token="tok")

    def test_run_returns_when_no_job_exists(self):
        Worker._testing_reset_subclass()

        class _Sub(Worker):
            def process(self, job):
                return "ok", None

        _Sub().run()

    def test_run_by_pk_processes_job(self):
        Worker._testing_reset_subclass()

        class _Sub(Worker):
            def process(self, job):
                return "result", None

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.raw_output, "result")

    def test_run_by_pk_missing_job_returns(self):
        Worker._testing_reset_subclass()

        class _Sub(Worker):
            def process(self, job):
                return "ok", None

        _Sub().run(job_pk=99999)
        self.assertFalse(Job.objects.exists())

    def test_run_by_pk_skips_already_processed_job(self):
        Worker._testing_reset_subclass()

        class _Sub(Worker):
            def process(self, job):
                return "overwritten", None

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        Job.objects.filter(pk=job.pk).update(
            raw_output="existing",
            processing_finished_at="2024-01-01 00:00:00+00",
        )
        _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.raw_output, "existing")

    def test_save_result_with_error(self):
        Worker._testing_reset_subclass()

        class _Sub(Worker):
            def process(self, job):
                return None, "handled error"

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertEqual(job.error, "handled error")
        self.assertIsNotNone(job.processing_finished_at)

    def test_run_raises_and_saves_error_when_process_fails(self):
        Worker._testing_reset_subclass()

        class _Sub(Worker):
            def process(self, job):
                raise RuntimeError("boom")

        job = Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        with self.assertRaises(RuntimeError):
            _Sub().run(job_pk=job.pk)
        job.refresh_from_db()
        self.assertIsNotNone(job.error)
        self.assertIsNotNone(job.processing_finished_at)

    def test_poll_without_select_related(self):
        Worker._testing_reset_subclass()

        class _Sub(Worker):
            poll_filters = {"bot__name": self.bot.name}

            def process(self, job):
                return "ok", None

        Job.objects.create(bot=self.bot, reply_target="1", raw_input="hi")
        _Sub().run()
        self.assertTrue(
            Job.objects.filter(processing_finished_at__isnull=False).exists()
        )
