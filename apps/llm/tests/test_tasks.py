"""Worker task tests — moved from engine/jobs/tests/test_tasks_branches.py."""

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase

from apps.llm.models import Worker as WorkerModel
from apps.llm.tasks import worker
from engine.telegram.models import Bot, Job


class WorkerTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = datetime.now(dt_timezone.utc)
        from apps.inference.models import Profile, Provider
        from apps.library.models import Skill, Wrapper

        skill = Skill.objects.create(name="task-skill", content="s")
        wrapper = Wrapper.objects.create(name="task-wrapper", skill=skill, content="w")
        provider = Provider.objects.create(
            name="task-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(
            provider=provider,
            name="task-profile",
            model="gpt-4o",
        )
        cls.bot = Bot.objects.create(
            name="task-bot",
            telegram_api_token="telegram-token",
        )
        WorkerModel.objects.create(
            bot=cls.bot,
            profile=profile,
            wrapper=wrapper,
        )

    def test_worker_returns_when_no_job_exists(self):
        worker()
        self.assertFalse(Job.objects.exists())

    @patch("apps.llm.worker.call_llm", return_value="llm output")
    def test_worker_stores_successful_output(self, call_llm_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        worker()
        job.refresh_from_db()
        self.assertEqual(job.raw_output, "llm output")
        self.assertIsNone(job.error)
        self.assertIsNotNone(job.processing_started_at)
        self.assertIsNotNone(job.processing_finished_at)

    @patch("apps.llm.worker.call_llm", return_value="oldest output")
    def test_worker_processes_oldest_pending_job_first(self, call_llm_mock):
        older = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="older",
        )
        newer = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="newer",
        )
        Job.objects.filter(pk=older.pk).update(
            created_at=self.now - timedelta(seconds=10)
        )
        Job.objects.filter(pk=newer.pk).update(created_at=self.now)
        worker()
        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(older.raw_output, "oldest output")
        self.assertIsNone(newer.raw_output)
        call_llm_mock.assert_called_once()

    @patch("apps.llm.worker.call_llm", return_value="pending output")
    def test_worker_ignores_finished_jobs_without_started_timestamp(
        self,
        call_llm_mock,
    ):
        finished = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="finished",
            raw_output="already done",
            processing_finished_at=self.now,
        )
        pending = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="pending",
        )
        Job.objects.filter(pk=finished.pk).update(
            created_at=self.now - timedelta(seconds=10)
        )
        Job.objects.filter(pk=pending.pk).update(created_at=self.now)
        worker()
        finished.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(finished.raw_output, "already done")
        self.assertEqual(pending.raw_output, "pending output")
        call_llm_mock.assert_called_once()

    @patch("apps.llm.worker.call_llm", side_effect=RuntimeError("llm down"))
    def test_worker_stores_error_and_raises(self, call_llm_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        with self.assertRaisesRegex(RuntimeError, "llm down"):
            worker()
        job.refresh_from_db()
        self.assertEqual(job.error, "llm down")
        self.assertIsNone(job.raw_output)
        self.assertIsNotNone(job.processing_finished_at)

    @patch("apps.llm.worker.call_llm", return_value="requeued output")
    def test_worker_requeues_stale_started_job(self, call_llm_mock):
        _STALE_SECONDS = 3600
        stale_started_at = self.now - timedelta(seconds=_STALE_SECONDS + 1)
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
            processing_started_at=stale_started_at,
        )
        worker()
        job.refresh_from_db()
        self.assertEqual(job.raw_output, "requeued output")
        self.assertIsNone(job.error)
        self.assertIsNotNone(job.processing_finished_at)
        self.assertGreater(job.processing_started_at, stale_started_at)
        call_llm_mock.assert_called_once()

    @patch(
        "engine.processing.models.transaction.atomic",
        side_effect=RuntimeError("db down"),
    )
    def test_worker_raises_outer_failure(self, atomic_mock):
        with self.assertRaisesRegex(RuntimeError, "db down"):
            worker()

    @patch("engine.processing.models.logger")
    def test_worker_returns_when_job_pk_not_found(self, logger):
        worker(job_pk=9999)
        logger.warning.assert_called_once()

    @patch("apps.llm.worker.call_llm", return_value="llm output")
    def test_worker_processes_specific_job_by_pk(self, call_llm_mock):
        pending = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="pending",
        )
        other = Job.objects.create(
            bot=self.bot,
            reply_target="456",
            raw_input="other",
        )
        worker(job_pk=pending.pk)
        pending.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(pending.raw_output, "llm output")
        self.assertIsNone(other.processing_finished_at)

    def test_worker_fails_when_worker_disabled_by_pk(self):
        bot2 = Bot.objects.create(
            name="disabled-worker-bot",
            telegram_api_token="tok2",
        )
        WorkerModel.objects.create(
            bot=bot2,
            profile=self.bot.worker.profile,
            wrapper=self.bot.worker.wrapper,
            enabled=False,
        )
        job = Job.objects.create(
            bot=bot2,
            reply_target="123",
            raw_input="disabled",
        )
        worker(job_pk=job.pk)
        job.refresh_from_db()
        self.assertIsNotNone(job.processing_finished_at)
        self.assertIn("Worker disabled", job.error)

    def test_worker_fails_when_worker_missing_by_pk(self):
        bot2 = Bot.objects.create(
            name="no-worker-bot",
            telegram_api_token="tok3",
        )
        job = Job.objects.create(
            bot=bot2,
            reply_target="123",
            raw_input="missing",
        )
        worker(job_pk=job.pk)
        job.refresh_from_db()
        self.assertIsNotNone(job.processing_finished_at)
        self.assertIn("No worker configured", job.error)

    @patch("apps.llm.worker.call_llm", return_value="llm output")
    def test_worker_skips_already_finished_job_by_pk(self, call_llm_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="done",
            raw_output="already done",
            processing_finished_at=self.now,
        )
        worker(job_pk=job.pk)
        call_llm_mock.assert_not_called()
