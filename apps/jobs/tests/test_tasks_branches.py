from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.models import Job
from apps.jobs.tasks import (
    Q2_LLM_STALE_JOB_SECONDS,
    llm_worker,
    telegram_deliver,
    telegram_ingest,
)
from apps.library.models import Skill, Wrapper


class PipelineTaskBranchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = datetime.now(dt_timezone.utc)
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
            profile=profile,
            wrapper=wrapper,
        )

    @patch("apps.jobs.tasks.get_updates", return_value=[])
    def test_ingest_no_updates_leaves_offset_unchanged(self, get_updates):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 0)
        get_updates.assert_called_once_with("telegram-token", offset=None)

    @patch("apps.jobs.tasks.get_updates", return_value=[{"update_id": 10}])
    def test_ingest_with_only_non_message_updates_creates_no_jobs(self, get_updates):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 11)
        self.assertFalse(Job.objects.exists())

    @patch("apps.jobs.tasks.send_message")
    @patch(
        "apps.jobs.tasks.get_updates",
        return_value=[
            {
                "update_id": 10,
                "message": {"message_id": 7, "chat": {"id": 123}, "text": "/start"},
            },
            {
                "update_id": 11,
                "message": {"message_id": 8, "chat": {"id": 123}, "text": "   "},
            },
            {
                "update_id": 12,
                "message": {"message_id": 9, "chat": {"id": 123}, "sticker": {}},
            },
            {
                "update_id": 13,
                "message": {"message_id": 10, "chat": {"id": 123}, "text": "hello"},
            },
        ],
    )
    def test_ingest_ignores_non_prompt_messages(self, get_updates, send_message):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 14)
        self.assertEqual(
            list(Job.objects.values_list("raw_input", flat=True)), ["hello"]
        )
        send_message.assert_called_once()

    @patch("apps.jobs.tasks.logger")
    @patch("apps.jobs.tasks.send_message", side_effect=RuntimeError("ack down"))
    @patch(
        "apps.jobs.tasks.get_updates",
        return_value=[
            {"update_id": 10},
            {
                "update_id": 11,
                "message": {"message_id": 7, "chat": {"id": 123}, "text": "hello"},
            },
        ],
    )
    def test_ingest_skips_non_message_update_and_logs_ack_failure(
        self,
        get_updates,
        send_message,
        logger,
    ):
        telegram_ingest()

        self.assertTrue(Job.objects.filter(raw_input="hello").exists())
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 12)
        send_message.assert_called_once()
        logger.error.assert_called_once()

    @patch("apps.jobs.tasks.logger")
    @patch("apps.jobs.tasks.get_updates", side_effect=RuntimeError("telegram down"))
    def test_ingest_logs_bot_failure(self, get_updates, logger):
        telegram_ingest()

        logger.error.assert_called_once()

    @patch("apps.jobs.tasks.logger")
    @patch("apps.jobs.tasks.Bot.objects.filter", side_effect=RuntimeError("db down"))
    def test_ingest_logs_global_failure(self, filter_mock, logger):
        telegram_ingest()

        logger.critical.assert_called_once()

    def test_llm_worker_returns_when_no_job_exists(self):
        llm_worker()

        self.assertFalse(Job.objects.exists())

    @patch("apps.jobs.tasks.call_llm", return_value="llm output")
    def test_llm_worker_stores_successful_output(self, call_llm_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )

        llm_worker()

        job.refresh_from_db()
        self.assertEqual(job.raw_output, "llm output")
        self.assertIsNone(job.error)
        self.assertIsNotNone(job.llm_started_at)
        self.assertIsNotNone(job.llm_finished_at)

    @patch("apps.jobs.tasks.call_llm", return_value="oldest output")
    def test_llm_worker_processes_oldest_pending_job_first(self, call_llm_mock):
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

        llm_worker()

        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertEqual(older.raw_output, "oldest output")
        self.assertIsNone(newer.raw_output)
        call_llm_mock.assert_called_once()

    @patch("apps.jobs.tasks.call_llm", return_value="pending output")
    def test_llm_worker_ignores_finished_jobs_without_started_timestamp(
        self,
        call_llm_mock,
    ):
        finished = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="finished",
            raw_output="already done",
            llm_finished_at=self.now,
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

        llm_worker()

        finished.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(finished.raw_output, "already done")
        self.assertEqual(pending.raw_output, "pending output")
        call_llm_mock.assert_called_once()

    @patch("apps.jobs.tasks.call_llm", side_effect=RuntimeError("llm down"))
    def test_llm_worker_stores_error(self, call_llm_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )

        llm_worker()

        job.refresh_from_db()
        self.assertEqual(job.error, "llm down")
        self.assertIsNone(job.raw_output)
        self.assertIsNotNone(job.llm_finished_at)

    @patch("apps.jobs.tasks.call_llm", return_value="requeued output")
    def test_llm_worker_requeues_stale_started_job(self, call_llm_mock):
        stale_started_at = self.now - timedelta(seconds=Q2_LLM_STALE_JOB_SECONDS + 1)
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
            llm_started_at=stale_started_at,
        )

        llm_worker()

        job.refresh_from_db()
        self.assertEqual(job.raw_output, "requeued output")
        self.assertIsNone(job.error)
        self.assertIsNotNone(job.llm_finished_at)
        self.assertGreater(job.llm_started_at, stale_started_at)
        call_llm_mock.assert_called_once()

    @patch("apps.jobs.tasks.logger")
    @patch("apps.jobs.tasks.transaction.atomic", side_effect=RuntimeError("db down"))
    def test_llm_worker_logs_outer_failure(self, atomic_mock, logger):
        llm_worker()

        logger.error.assert_called_once()

    @patch("apps.jobs.tasks.send_document", side_effect=RuntimeError("telegram down"))
    def test_deliver_stores_error_when_send_fails(self, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hi",
            raw_output="short response",
            llm_finished_at=self.now,
        )

        telegram_deliver()

        job.refresh_from_db()
        self.assertIsNone(job.sent_at)
        self.assertEqual(job.error, "telegram down")

    def test_deliver_returns_when_no_job_exists(self):
        telegram_deliver()

        self.assertFalse(Job.objects.filter(sent_at__isnull=False).exists())

    @patch("apps.jobs.tasks.logger")
    @patch("apps.jobs.tasks.transaction.atomic", side_effect=RuntimeError("db down"))
    def test_deliver_logs_outer_failure(self, atomic_mock, logger):
        telegram_deliver()

        logger.error.assert_called_once()
