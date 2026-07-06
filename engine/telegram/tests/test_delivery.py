from datetime import datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase

from engine.telegram.client import TELEGRAM_MESSAGE_CHAR_LIMIT
from engine.telegram.models import Bot, Job
from engine.telegram.tasks import (
    telegram_deliver,
    telegram_ingest,
)


class TelegramDeliveryTests(TestCase):
    """Test Telegram delivery method selection."""

    @classmethod
    def setUpTestData(cls):
        cls.now = datetime.now(dt_timezone.utc)
        cls.bot = Bot.objects.create(
            name="delivery-bot",
            telegram_api_token="telegram-token",
        )

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_short_response_sent_as_text_document(self, send_message, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output="short response",
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_not_called()
        send_document.assert_called_once_with(
            "telegram-token",
            "123",
            "short response",
            f"response-{job.pk}.txt",
            "text/plain",
            caption="Response is attached as a text file.",
            reply_to_message_id=456,
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.delivery_finished_at)
        self.assertIsNone(job.processing_error)

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_markdown_response_sent_as_markdown_document(
        self,
        send_message,
        send_document,
    ):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output="*bold*",
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_not_called()
        send_document.assert_called_once_with(
            "telegram-token",
            "123",
            "*bold*",
            f"response-{job.pk}.md",
            "text/markdown",
            caption="Response is attached as a text file.",
            reply_to_message_id=456,
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.delivery_finished_at)
        self.assertIsNone(job.processing_error)

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_html_response_sent_as_html_document(self, send_message, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output="<b>bold</b>",
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_not_called()
        send_document.assert_called_once_with(
            "telegram-token",
            "123",
            "<b>bold</b>",
            f"response-{job.pk}.html",
            "text/html",
            caption="Response is attached as a text file.",
            reply_to_message_id=456,
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.delivery_finished_at)
        self.assertIsNone(job.processing_error)

    @patch("engine.telegram.tasks.send_message")
    @patch("engine.telegram.tasks.get_updates")
    def test_ingest_appends_to_intake_buffer(self, get_updates, send_message):
        get_updates.return_value = [
            {
                "update_id": 100,
                "message": {
                    "message_id": 456,
                    "chat": {"id": 123},
                    "date": 1700000000,
                    "text": "hello",
                },
            }
        ]

        telegram_ingest()

        from engine.telegram.models import IntakeBuffer

        buffer = IntakeBuffer.objects.get(text="hello")
        self.assertEqual(buffer.chat_id, "123")
        self.assertEqual(buffer.reply_to_message_id, 456)
        self.assertEqual(buffer.last_message_ts, 1700000000)
        self.assertFalse(Job.objects.exists())

    def test_accept_message_without_message_id(self):
        from engine.telegram.intake import accept_telegram_message

        buffer = accept_telegram_message(
            self.bot, "999", None, 1700000000, "no-message-id"
        )
        self.assertIsNone(buffer.reply_to_message_id)
        self.assertEqual(buffer.text, "no-message-id")

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_long_response_sent_as_document(self, send_message, send_document):
        output = ("x" * (TELEGRAM_MESSAGE_CHAR_LIMIT + 1)) + "\x08"
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output=output,
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_not_called()
        send_document.assert_called_once_with(
            "telegram-token",
            "123",
            output,
            f"response-{job.pk}.txt",
            "text/plain",
            caption="Response is attached as a text file.",
            reply_to_message_id=456,
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.delivery_finished_at)
        self.assertIsNone(job.processing_error)

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_long_markdown_response_sent_as_markdown_document(
        self,
        send_message,
        send_document,
    ):
        output = "**bold**\n" + ("x" * TELEGRAM_MESSAGE_CHAR_LIMIT)
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output=output,
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_not_called()
        send_document.assert_called_once_with(
            "telegram-token",
            "123",
            output,
            f"response-{job.pk}.md",
            "text/markdown",
            caption="Response is attached as a text file.",
            reply_to_message_id=456,
        )

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_long_html_response_sent_as_html_document(
        self,
        send_message,
        send_document,
    ):
        output = "<b>bold</b>\n" + ("x" * TELEGRAM_MESSAGE_CHAR_LIMIT)
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output=output,
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_not_called()
        send_document.assert_called_once_with(
            "telegram-token",
            "123",
            output,
            f"response-{job.pk}.html",
            "text/html",
            caption="Response is attached as a text file.",
            reply_to_message_id=456,
        )

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_deliver_by_pk_sends_normal_response(self, send_message, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hi",
            raw_output="output",
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver(job_pk=job.pk)

        send_document.assert_called_once()
        job.refresh_from_db()
        self.assertIsNotNone(job.delivery_finished_at)

    @patch("engine.telegram.tasks.logger")
    def test_deliver_by_pk_returns_when_job_not_found(self, logger):
        telegram_deliver(job_pk=9999)

        logger.warning.assert_called_once()

    @patch("engine.telegram.tasks.logger")
    def test_deliver_by_pk_skips_already_delivered_job(self, logger):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="done",
            raw_output="done",
            processing_started_at=self.now,
            processing_finished_at=self.now,
            delivery_started_at=self.now,
            delivery_finished_at=self.now,
        )

        telegram_deliver(job_pk=job.pk)

        logger.debug.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.delivery_finished_at, self.now)

    def test_deliver_poll_returns_when_no_jobs(self):
        telegram_deliver()

    @patch("engine.telegram.tasks.send_document")
    @patch("engine.telegram.tasks.send_message")
    def test_deliver_sends_error_when_job_has_error(self, send_message, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hi",
            raw_output="output",
            processing_error="Something went wrong",
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        telegram_deliver()

        send_document.assert_not_called()
        send_message.assert_called_once_with(
            "telegram-token",
            "123",
            "Something went wrong",
            reply_to_message_id=None,
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.delivery_finished_at)

    @patch("engine.telegram.tasks.send_document", side_effect=RuntimeError("api down"))
    @patch("engine.telegram.tasks.send_message")
    def test_deliver_raises_when_send_fails(self, send_message, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hi",
            raw_output="output",
            processing_started_at=self.now,
            processing_finished_at=self.now,
        )

        with self.assertRaisesRegex(RuntimeError, "api down"):
            telegram_deliver()

        job.refresh_from_db()
        self.assertIsNone(job.processing_error)
        self.assertIn("api down", job.delivery_error)
