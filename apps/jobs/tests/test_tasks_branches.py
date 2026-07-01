from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, override_settings

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

    @patch(
        "apps.jobs.tasks.Bot.objects.select_for_update", return_value=Bot.objects.none()
    )
    def test_ingest_skips_bot_locked_by_another_worker(self, mock_sfu):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 0)
        self.assertFalse(Job.objects.exists())

    def test_ingest_skips_bot_deleted_between_transactions(self):
        def _delete_and_return(*args, **kwargs):
            self.bot.delete()
            return [
                {
                    "update_id": 10,
                    "message": {"message_id": 1, "chat": {"id": 123}, "text": "hello"},
                }
            ]

        with patch("apps.jobs.tasks.get_updates", side_effect=_delete_and_return):
            telegram_ingest()

        self.assertFalse(Job.objects.exists())

    def test_ingest_skips_when_offset_already_advanced(self):
        self.bot.telegram_update_offset = 100
        self.bot.save(update_fields=["telegram_update_offset"])

        with patch(
            "apps.jobs.tasks.get_updates",
            return_value=[
                {
                    "update_id": 50,
                    "message": {"message_id": 1, "chat": {"id": 123}, "text": "hello"},
                },
            ],
        ):
            telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 100)
        self.assertFalse(Job.objects.exists())

    def test_ingest_skips_offset_already_advanced_inside_merged_block(self):
        self.bot.telegram_update_offset = 0
        self.bot.save(update_fields=["telegram_update_offset"])

        def advance_offset_and_return(*args, **kwargs):
            Bot.objects.filter(pk=self.bot.pk).update(telegram_update_offset=20)
            return [
                {
                    "update_id": 15,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 123},
                        "text": "hello",
                    },
                },
            ]

        with patch(
            "apps.jobs.tasks.get_updates",
            side_effect=advance_offset_and_return,
        ):
            telegram_ingest()

        self.bot.refresh_from_db()
        # Offset advanced by the concurrent worker, not by this cycle
        self.assertEqual(self.bot.telegram_update_offset, 20)
        self.assertFalse(Job.objects.exists())

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
    def test_llm_worker_stores_error_and_raises(self, call_llm_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )

        with self.assertRaisesRegex(RuntimeError, "llm down"):
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

    @patch("apps.jobs.tasks.transaction.atomic", side_effect=RuntimeError("db down"))
    def test_llm_worker_raises_outer_failure(self, atomic_mock):
        with self.assertRaisesRegex(RuntimeError, "db down"):
            llm_worker()

    @patch("apps.jobs.tasks.send_document", side_effect=RuntimeError("telegram down"))
    def test_deliver_stores_error_and_raises_when_send_fails(self, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hi",
            raw_output="short response",
            llm_finished_at=self.now,
        )

        with self.assertRaisesRegex(RuntimeError, "telegram down"):
            telegram_deliver()

        job.refresh_from_db()
        self.assertIsNone(job.delivery_finished_at)
        self.assertEqual(job.error, "telegram down")

    @patch("apps.jobs.tasks.send_document")
    def test_deliver_sends_oldest_finished_job_first(self, send_document):
        newer = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="newer",
            raw_output="newer response",
            llm_finished_at=self.now,
        )
        older = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="older",
            raw_output="older response",
            llm_finished_at=self.now - timedelta(seconds=10),
        )

        telegram_deliver()

        older.refresh_from_db()
        newer.refresh_from_db()
        self.assertIsNotNone(older.delivery_finished_at)
        self.assertIsNone(newer.delivery_finished_at)
        send_document.assert_called_once()
        self.assertEqual(send_document.call_args.args[2], "older response")

    @patch("apps.jobs.tasks.send_document")
    def test_deliver_skips_job_already_being_delivered(self, send_document):
        in_progress = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="in progress",
            raw_output="in progress response",
            llm_finished_at=self.now - timedelta(seconds=10),
            delivery_started_at=self.now,
        )
        ready = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="ready",
            raw_output="ready response",
            llm_finished_at=self.now,
        )

        telegram_deliver()

        in_progress.refresh_from_db()
        ready.refresh_from_db()
        self.assertIsNone(in_progress.delivery_finished_at)
        self.assertIsNotNone(ready.delivery_finished_at)
        send_document.assert_called_once()
        self.assertEqual(send_document.call_args.args[2], "ready response")

    @patch("apps.jobs.tasks.send_document")
    def test_deliver_does_not_retry_stale_delivery(self, send_document):
        stale_started_at = self.now - timedelta(hours=2)
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="stale",
            raw_output="stale response",
            llm_finished_at=self.now,
            delivery_started_at=stale_started_at,
        )

        telegram_deliver()

        job.refresh_from_db()
        self.assertIsNone(job.delivery_finished_at)
        self.assertEqual(job.delivery_started_at, stale_started_at)
        send_document.assert_not_called()

    def test_deliver_returns_when_no_job_exists(self):
        telegram_deliver()

        self.assertFalse(
            Job.objects.filter(delivery_finished_at__isnull=False).exists()
        )

    @patch("apps.jobs.tasks.send_message")
    def test_deliver_sends_error_as_message_when_job_has_error(self, send_message_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hi",
            llm_finished_at=self.now,
            error="something went wrong",
        )

        telegram_deliver()

        job.refresh_from_db()
        self.assertIsNotNone(job.delivery_finished_at)
        send_message_mock.assert_called_once_with(
            self.bot.telegram_api_token,
            "123",
            "something went wrong",
            reply_to_message_id=None,
        )

    @patch("apps.jobs.tasks.transaction.atomic", side_effect=RuntimeError("db down"))
    def test_deliver_raises_outer_failure(self, atomic_mock):
        with self.assertRaisesRegex(RuntimeError, "db down"):
            telegram_deliver()

    def test_deliver_returns_when_job_pk_not_found(self):
        telegram_deliver(job_pk=9999)

        self.assertFalse(
            Job.objects.filter(delivery_finished_at__isnull=False).exists()
        )

    @patch("apps.jobs.tasks.send_document")
    def test_deliver_processes_specific_job_by_pk(self, send_document):
        pending = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="pending",
            raw_output="pending response",
            llm_finished_at=self.now,
        )
        other = Job.objects.create(
            bot=self.bot,
            reply_target="456",
            raw_input="other",
            raw_output="other response",
            llm_finished_at=self.now,
        )

        telegram_deliver(job_pk=pending.pk)

        pending.refresh_from_db()
        other.refresh_from_db()
        self.assertIsNotNone(pending.delivery_finished_at)
        self.assertIsNone(other.delivery_finished_at)
        send_document.assert_called_once()

    @patch("apps.jobs.tasks.send_document")
    def test_deliver_skips_already_delivered_job_by_pk(self, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="done",
            raw_output="done response",
            llm_finished_at=self.now,
            delivery_started_at=self.now,
            delivery_finished_at=self.now,
        )
        telegram_deliver(job_pk=job.pk)

        telegram_deliver(job_pk=job.pk)

        send_document.assert_not_called()

    @patch("apps.jobs.tasks.logger")
    def test_llm_worker_returns_when_job_pk_not_found(self, logger):
        llm_worker(job_pk=9999)

        logger.warning.assert_called_once()

    @patch("apps.jobs.tasks.call_llm", return_value="llm output")
    def test_llm_worker_processes_specific_job_by_pk(self, call_llm_mock):
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

        llm_worker(job_pk=pending.pk)

        pending.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(pending.raw_output, "llm output")
        self.assertIsNone(other.llm_finished_at)

    @patch("apps.jobs.tasks.call_llm", return_value="llm output")
    def test_llm_worker_skips_already_finished_job_by_pk(self, call_llm_mock):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="done",
            raw_output="already done",
            llm_finished_at=self.now,
        )

        llm_worker(job_pk=job.pk)

        call_llm_mock.assert_not_called()


class WebhookManagementTests(TestCase):
    """Tests for _manage_webhook_for_bot called inside telegram_ingest."""

    @classmethod
    def setUpTestData(cls):
        cls.now = datetime.now(dt_timezone.utc)
        skill = Skill.objects.create(name="webhook-skill", content="s")
        wrapper = Wrapper.objects.create(
            name="webhook-wrapper", skill=skill, content="w"
        )
        provider = Provider.objects.create(
            name="webhook-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(
            provider=provider,
            name="webhook-profile",
            model="gpt-4o",
        )
        cls.bot = Bot.objects.create(
            name="webhook-bot",
            telegram_api_token="telegram-token",
            profile=profile,
            wrapper=wrapper,
        )

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch(
        "apps.jobs.tasks.get_webhook_info",
        return_value={"url": "", "pending_update_count": 0},
    )
    @patch("apps.jobs.tasks.set_webhook", return_value={})
    def test_webhook_auto_registers_when_not_set(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        telegram_ingest()

        mock_set.assert_called_once_with(
            "telegram-token",
            "https://example.com/webhook/telegram-token/",
        )
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch(
        "apps.jobs.tasks.get_webhook_info",
        return_value={
            "url": "https://example.com/webhook/telegram-token/",
            "pending_update_count": 0,
        },
    )
    @patch("apps.jobs.tasks.set_webhook")
    def test_webhook_skips_re_registration_when_healthy(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        telegram_ingest()

        mock_set.assert_not_called()
        self.bot.refresh_from_db()
        # webhook_enabled_at is set because it was None and webhook is healthy
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch(
        "apps.jobs.tasks.get_webhook_info",
        return_value={
            "url": "https://example.com/webhook/telegram-token/",
            "pending_update_count": 10,
        },
    )
    @patch("apps.jobs.tasks.delete_webhook", return_value={})
    def test_webhook_falls_back_when_pending_threshold_exceeded(
        self,
        mock_delete,
        mock_info,
        mock_updates,
    ):
        telegram_ingest()

        mock_delete.assert_called_once_with("telegram-token")
        self.bot.refresh_from_db()
        self.assertIsNone(self.bot.webhook_enabled_at)
        self.assertIsNotNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch(
        "apps.jobs.tasks.get_webhook_info",
        return_value={
            "url": "https://example.com/webhook/telegram-token/",
            "pending_update_count": 0,
            "last_error_message": "Wrong URL",
        },
    )
    @patch("apps.jobs.tasks.set_webhook", return_value={})
    def test_webhook_re_registers_on_last_error(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        telegram_ingest()

        mock_set.assert_called_once()
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch("apps.jobs.tasks.get_webhook_info")
    @patch("apps.jobs.tasks.set_webhook", side_effect=RuntimeError("API down"))
    @patch("apps.jobs.tasks.delete_webhook", return_value={})
    def test_webhook_falls_back_when_registration_fails(
        self,
        mock_delete,
        mock_set,
        mock_info,
        mock_updates,
    ):
        mock_info.return_value = {
            "url": "",
            "pending_update_count": 0,
        }
        telegram_ingest()

        mock_delete.assert_called_once_with("telegram-token")
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch("apps.jobs.tasks.get_webhook_info")
    def test_webhook_respects_cooldown_after_fallback(
        self,
        mock_info,
        mock_updates,
    ):
        self.bot.webhook_disabled_at = self.now
        self.bot.save(update_fields=["webhook_disabled_at"])

        telegram_ingest()

        # Cooldown (300s) is active — no webhook API calls
        mock_info.assert_not_called()

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch("apps.jobs.tasks.get_webhook_info")
    @patch("apps.jobs.tasks.set_webhook")
    def test_webhook_retries_after_cooldown_expires(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        past = self.now - timedelta(seconds=400)
        self.bot.webhook_disabled_at = past
        self.bot.save(update_fields=["webhook_disabled_at"])

        mock_info.return_value = {
            "url": "",
            "pending_update_count": 0,
        }
        mock_set.return_value = {}

        telegram_ingest()

        mock_info.assert_called_once()
        mock_set.assert_called_once()
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch(
        "apps.jobs.tasks.get_webhook_info",
        return_value={
            "url": "https://example.com/webhook/telegram-token/",
            "pending_update_count": 0,
        },
    )
    @patch("apps.jobs.tasks.set_webhook")
    def test_webhook_does_not_update_when_already_registered(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        self.bot.webhook_enabled_at = self.now
        self.bot.save(update_fields=["webhook_enabled_at"])

        telegram_ingest()

        mock_set.assert_not_called()
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.webhook_enabled_at, self.now)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch(
        "apps.jobs.tasks.get_webhook_info", side_effect=RuntimeError("API unreachable")
    )
    def test_webhook_handles_info_api_error(
        self,
        mock_info,
        mock_updates,
    ):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertIsNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("apps.jobs.tasks.get_updates", return_value=[])
    @patch(
        "apps.jobs.tasks.get_webhook_info",
        return_value={
            "url": "",
            "pending_update_count": 0,
        },
    )
    @patch("apps.jobs.tasks.set_webhook", side_effect=RuntimeError("register failed"))
    @patch("apps.jobs.tasks.delete_webhook", side_effect=RuntimeError("delete failed"))
    def test_webhook_handles_delete_error_during_fallback(
        self,
        mock_delete,
        mock_set,
        mock_info,
        mock_updates,
    ):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_disabled_at)
