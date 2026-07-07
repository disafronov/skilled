from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from engine.telegram.models import Bot, IntakeBuffer, Job
from engine.telegram.tasks import (
    TelegramAPIError,
    telegram_ack,
    telegram_ingest,
    telegram_setup,
)


class PipelineTaskBranchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = datetime.now(dt_timezone.utc)
        cls.bot = Bot.objects.create(
            name="task-bot",
            telegram_api_token="telegram-token",
        )

    @patch(
        "engine.telegram.tasks.Bot.objects.select_for_update",
        return_value=Bot.objects.none(),
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

        with patch("engine.telegram.tasks.get_updates", side_effect=_delete_and_return):
            telegram_ingest()

        self.assertFalse(Job.objects.exists())

    def test_ingest_skips_when_offset_already_advanced(self):
        self.bot.telegram_update_offset = 100
        self.bot.save(update_fields=["telegram_update_offset"])

        with patch(
            "engine.telegram.tasks.get_updates",
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
            "engine.telegram.tasks.get_updates",
            side_effect=advance_offset_and_return,
        ):
            telegram_ingest()

        self.bot.refresh_from_db()
        # Offset advanced by the concurrent worker, not by this cycle
        self.assertEqual(self.bot.telegram_update_offset, 20)
        self.assertFalse(Job.objects.exists())

    @patch("engine.telegram.tasks.get_updates", return_value=[])
    def test_ingest_no_updates_leaves_offset_unchanged(self, get_updates):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 0)
        get_updates.assert_called_once_with("telegram-token", offset=None)

    @patch("engine.telegram.tasks.get_updates", return_value=[{"update_id": 10}])
    def test_ingest_with_only_non_message_updates_creates_no_jobs(self, get_updates):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 11)
        self.assertFalse(Job.objects.exists())

    @patch("engine.telegram.tasks.send_message")
    @patch(
        "engine.telegram.tasks.get_updates",
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
                "message": {
                    "message_id": 10,
                    "chat": {"id": 123},
                    "date": 1700000000,
                    "text": "hello",
                },
            },
        ],
    )
    def test_ingest_ignores_non_prompt_messages(self, get_updates, send_message):
        telegram_ingest()

        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 14)
        self.assertEqual(
            list(IntakeBuffer.objects.values_list("text", flat=True)), ["hello"]
        )
        self.assertFalse(Job.objects.exists())

    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks.get_updates",
        return_value=[
            {"update_id": 10},
            {
                "update_id": 11,
                "message": {
                    "message_id": 7,
                    "chat": {"id": 123},
                    "date": 1700000000,
                    "text": "hello",
                },
            },
        ],
    )
    def test_ingest_skips_non_message_update(
        self,
        get_updates,
        logger,
    ):
        telegram_ingest()

        self.assertTrue(IntakeBuffer.objects.filter(text="hello").exists())
        self.assertFalse(Job.objects.exists())
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 12)

    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks.get_updates",
        side_effect=TelegramAPIError("telegram down", status_code=500),
    )
    def test_ingest_logs_bot_failure(self, get_updates, logger):
        telegram_ingest()

        logger.error.assert_called_once()

    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks.get_updates",
        side_effect=TelegramAPIError(
            "Conflict: terminated by setWebhook request", status_code=409
        ),
    )
    def test_ingest_logs_warning_on_409_conflict(self, get_updates, logger):
        telegram_ingest()

        logger.warning.assert_called_once()
        logger.error.assert_not_called()

    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks.get_updates",
        side_effect=ValueError("unexpected error"),
    )
    def test_ingest_logs_error_on_non_runtime_exception(self, get_updates, logger):
        telegram_ingest()

        logger.error.assert_called_once()

    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks.Bot.objects.filter", side_effect=RuntimeError("db down")
    )
    def test_ingest_logs_global_failure(self, filter_mock, logger):
        telegram_ingest()

        logger.critical.assert_called_once()

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    def test_ingest_skips_bot_with_active_webhook(self, get_updates):
        self.bot.webhook_enabled_at = self.now
        self.bot.save(update_fields=["webhook_enabled_at"])

        telegram_ingest()

        get_updates.assert_not_called()
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.telegram_update_offset, 0)


class WebhookManagementTests(TestCase):
    """Tests for _manage_webhook_for_bot called inside telegram_setup."""

    @classmethod
    def setUpTestData(cls):
        cls.now = datetime.now(dt_timezone.utc)
        cls.bot = Bot.objects.create(
            name="webhook-bot",
            telegram_api_token="telegram-token",
        )

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch(
        "engine.telegram.tasks.get_webhook_info",
        return_value={"url": "", "pending_update_count": 0},
    )
    @patch("engine.telegram.tasks.set_webhook", return_value={})
    def test_webhook_auto_registers_when_not_set(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        telegram_setup()

        self.bot.refresh_from_db()
        mock_set.assert_called_once_with(
            "telegram-token",
            "https://example.com/webhook/",
            secret_token=self.bot.webhook_secret,
        )
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch(
        "engine.telegram.tasks.get_webhook_info",
    )
    @patch("engine.telegram.tasks.set_webhook")
    def test_webhook_skips_re_registration_when_healthy(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        mock_info.return_value = {
            "url": "https://example.com/webhook/",
            "pending_update_count": 0,
        }
        telegram_setup()

        mock_set.assert_not_called()
        self.bot.refresh_from_db()
        # webhook_enabled_at is set because it was None and webhook is healthy
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch("engine.telegram.tasks.get_webhook_info")
    @patch("engine.telegram.tasks.delete_webhook", return_value={})
    def test_webhook_falls_back_when_pending_threshold_exceeded(
        self,
        mock_delete,
        mock_info,
        mock_updates,
    ):
        mock_info.return_value = {
            "url": "https://example.com/webhook/",
            "pending_update_count": 10,
        }
        telegram_setup()

        mock_delete.assert_called_once_with("telegram-token")
        self.bot.refresh_from_db()
        self.assertIsNone(self.bot.webhook_enabled_at)
        self.assertIsNotNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch("engine.telegram.tasks.get_webhook_info")
    @patch("engine.telegram.tasks.set_webhook", return_value={})
    def test_webhook_re_registers_on_last_error(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        mock_info.return_value = {
            "url": "https://example.com/webhook/",
            "pending_update_count": 0,
            "last_error_message": "Wrong URL",
        }
        telegram_setup()

        mock_set.assert_called_once()
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch("engine.telegram.tasks.get_webhook_info")
    @patch("engine.telegram.tasks.set_webhook", side_effect=RuntimeError("API down"))
    @patch("engine.telegram.tasks.delete_webhook", return_value={})
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
        telegram_setup()

        mock_delete.assert_called_once_with("telegram-token")
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch("engine.telegram.tasks.get_webhook_info")
    def test_webhook_respects_cooldown_after_fallback(
        self,
        mock_info,
        mock_updates,
    ):
        self.bot.webhook_disabled_at = self.now
        self.bot.save(update_fields=["webhook_disabled_at"])

        telegram_setup()

        # Cooldown (300s) is active — no webhook API calls
        mock_info.assert_not_called()

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch("engine.telegram.tasks.get_webhook_info")
    @patch("engine.telegram.tasks.set_webhook")
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

        telegram_setup()

        mock_info.assert_called_once()
        mock_set.assert_called_once()
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch("engine.telegram.tasks.get_webhook_info")
    @patch("engine.telegram.tasks.set_webhook")
    def test_webhook_does_not_update_when_already_registered(
        self,
        mock_set,
        mock_info,
        mock_updates,
    ):
        self.bot.webhook_enabled_at = self.now
        self.bot.save(update_fields=["webhook_enabled_at"])

        mock_info.return_value = {
            "url": "https://example.com/webhook/",
            "pending_update_count": 0,
        }
        telegram_setup()

        mock_set.assert_not_called()
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.webhook_enabled_at, self.now)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch(
        "engine.telegram.tasks.get_webhook_info",
        side_effect=RuntimeError("API unreachable"),
    )
    def test_webhook_handles_info_api_error(
        self,
        mock_info,
        mock_updates,
    ):
        telegram_setup()

        self.bot.refresh_from_db()
        self.assertIsNone(self.bot.webhook_enabled_at)
        self.assertIsNone(self.bot.webhook_disabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.get_updates", return_value=[])
    @patch(
        "engine.telegram.tasks.get_webhook_info",
        return_value={
            "url": "",
            "pending_update_count": 0,
        },
    )
    @patch(
        "engine.telegram.tasks.set_webhook", side_effect=RuntimeError("register failed")
    )
    @patch(
        "engine.telegram.tasks.delete_webhook",
        side_effect=RuntimeError("delete failed"),
    )
    def test_webhook_handles_delete_error_during_fallback(
        self,
        mock_delete,
        mock_set,
        mock_info,
        mock_updates,
    ):
        telegram_setup()

        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_disabled_at)

    @patch("engine.telegram.tasks.delete_webhook")
    def test_setup_cleans_up_webhook_for_disabled_bot(self, delete_webhook):
        self.bot.enabled = False
        self.bot.webhook_enabled_at = self.now
        self.bot.save()

        telegram_setup()

        delete_webhook.assert_called_once_with("telegram-token")
        self.bot.refresh_from_db()
        self.assertIsNone(self.bot.webhook_enabled_at)

    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks.delete_webhook",
        side_effect=RuntimeError("telegram down"),
    )
    def test_setup_logs_warning_when_disabled_bot_cleanup_fails(
        self, delete_webhook, logger
    ):
        self.bot.enabled = False
        self.bot.webhook_enabled_at = self.now
        self.bot.save()

        telegram_setup()

        delete_webhook.assert_called_once()
        logger.warning.assert_called_once()
        self.bot.refresh_from_db()
        self.assertIsNotNone(self.bot.webhook_enabled_at)

    @override_settings(BASE_URL="https://example.com")
    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks._manage_webhook_for_bot",
        side_effect=ValueError("boom"),
    )
    def test_setup_logs_error_when_bot_management_fails(
        self,
        manage_webhook,
        logger,
    ):
        telegram_setup()

        manage_webhook.assert_called_once()
        logger.error.assert_called_once()

    @patch("engine.telegram.tasks.logger")
    @patch(
        "engine.telegram.tasks.Bot.objects.filter", side_effect=RuntimeError("db down")
    )
    def test_setup_logs_global_failure(self, filter_mock, logger):
        telegram_setup()

        logger.critical.assert_called_once()

    @patch("engine.telegram.tasks.get_webhook_info")
    @patch("engine.telegram.tasks.set_webhook")
    def test_setup_skips_enabled_bots_without_base_url(
        self,
        mock_set,
        mock_info,
    ):
        telegram_setup()

        mock_info.assert_not_called()
        mock_set.assert_not_called()


class TelegramAckTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bot = Bot.objects.create(
            name="ack-bot",
            telegram_api_token="telegram-token",
        )

    @patch("engine.telegram.tasks.set_message_reaction")
    def test_ack_sends_reaction(self, mock_reaction):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hello",
        )

        telegram_ack(job.pk)

        mock_reaction.assert_called_once_with(
            "telegram-token",
            "123",
            456,
            "🤔",
        )

    @patch("engine.telegram.tasks.logger")
    def test_ack_warns_when_job_not_found(self, mock_logger):
        telegram_ack(999)

        mock_logger.warning.assert_called_once()

    @patch(
        "engine.telegram.tasks.set_message_reaction",
        side_effect=RuntimeError("ack down"),
    )
    @patch("engine.telegram.tasks.logger")
    def test_ack_logs_error_on_failure(self, mock_logger, mock_reaction):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=789,
            raw_input="hello",
        )

        telegram_ack(job.pk)

        mock_logger.error.assert_called_once()

    @override_settings(TELEGRAM_ACK_REACTION="")
    def test_ack_skipped_when_reaction_empty(self):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hello",
        )
        telegram_ack(job.pk)

    @patch("engine.telegram.tasks.set_message_reaction")
    def test_ack_skipped_when_no_reply_to_message_id(self, mock_reaction):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        telegram_ack(job.pk)
        mock_reaction.assert_not_called()


class IntakeFlushTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bot = Bot.objects.create(
            name="flush-bot",
            telegram_api_token="tok",
        )

    def test_flush_creates_job_from_due_buffer(self):
        old = timezone.now() - timedelta(seconds=60)
        buffer = IntakeBuffer.objects.create(
            bot=self.bot,
            chat_id="123",
            reply_to_message_id=99,
            text="hello world",
            last_message_ts=1700000000,
            last_received_at=old,
        )

        from engine.telegram.tasks import telegram_flush_intake_buffers

        telegram_flush_intake_buffers()

        buffer.refresh_from_db()
        self.assertIsNotNone(buffer.flushed_at)
        job = Job.objects.get()
        self.assertEqual(job.bot, self.bot)
        self.assertEqual(job.reply_target, "123")
        self.assertEqual(job.reply_to_message_id, 99)
        self.assertEqual(job.raw_input, "hello world")

    def test_flush_skips_fresh_buffer(self):
        now = timezone.now()
        IntakeBuffer.objects.create(
            bot=self.bot,
            chat_id="123",
            text="fresh",
            last_message_ts=1700000000,
            last_received_at=now,
        )

        from engine.telegram.tasks import telegram_flush_intake_buffers

        telegram_flush_intake_buffers()

        self.assertFalse(Job.objects.exists())
        self.assertEqual(
            IntakeBuffer.objects.filter(flushed_at__isnull=True).count(), 1
        )

    def test_flush_is_idempotent_when_already_flushed(self):
        old = timezone.now() - timedelta(seconds=60)
        buffer = IntakeBuffer.objects.create(
            bot=self.bot,
            chat_id="123",
            text="done",
            last_message_ts=1700000000,
            last_received_at=old,
            flushed_at=timezone.now(),
        )

        from engine.telegram.tasks import telegram_flush_intake_buffers

        telegram_flush_intake_buffers()

        self.assertFalse(Job.objects.exists())
        buffer.refresh_from_db()
        self.assertIsNotNone(buffer.flushed_at)

    def test_flush_skips_when_buffer_claimed_under_lock(self):
        old = timezone.now() - timedelta(seconds=60)
        IntakeBuffer.objects.create(
            bot=self.bot,
            chat_id="123",
            text="claimed",
            last_message_ts=1700000000,
            last_received_at=old,
        )

        from engine.telegram.tasks import telegram_flush_intake_buffers

        with patch.object(type(IntakeBuffer.objects), "select_for_update") as mock_sfu:
            mock_qs = MagicMock()
            mock_sfu.return_value = mock_qs
            mock_qs.filter.return_value.first.return_value = None
            telegram_flush_intake_buffers()

        self.assertFalse(Job.objects.exists())
