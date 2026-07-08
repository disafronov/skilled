"""Tests for bot webhook views."""

import json

from django.test import TestCase
from django.urls import reverse

from ..models import Bot, IntakeBuffer, Job


class WebhookViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.raw_token = "123456:ABC-DEF1234abcdef"
        cls.bot = Bot.objects.create(
            name="webhook-bot",
            telegram_api_token=cls.raw_token,
        )

    def _url(self) -> str:
        return reverse("webhook")

    def _post(self, data: dict, secret: str | None = None):
        headers = {
            "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": (
                secret if secret is not None else self.bot.webhook_secret
            ),
        }
        return self.client.post(
            self._url(),
            data=json.dumps(data),
            content_type="application/json",
            **headers,
        )

    def test_requires_post(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 405)

    def test_returns_400_on_invalid_json(self):
        response = self.client.post(
            self._url(), data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_skips_update_without_message(self):
        response = self._post({})
        self.assertEqual(response.status_code, 200)

    def test_skips_update_without_text(self):
        response = self._post({"message": {"chat": {"id": 1}}})
        self.assertEqual(response.status_code, 200)

    def test_skips_command_message(self):
        response = self._post({"message": {"chat": {"id": 1}, "text": "/start"}})
        self.assertEqual(response.status_code, 200)

    def test_skips_blank_text(self):
        response = self._post({"message": {"chat": {"id": 1}, "text": "   "}})
        self.assertEqual(response.status_code, 200)

    def test_returns_404_when_secret_missing(self):
        response = self._post(
            {"message": {"chat": {"id": 1}, "text": "hello"}},
            secret="",
        )
        self.assertEqual(response.status_code, 404)

    def test_returns_404_for_unknown_secret(self):
        response = self._post(
            {"message": {"chat": {"id": 1}, "text": "hello"}},
            secret="unknown-secret",
        )
        self.assertEqual(response.status_code, 404)

    def test_returns_404_when_bot_disabled(self):
        self.bot.enabled = False
        self.bot.save(update_fields=["enabled"])

        response = self._post({"message": {"chat": {"id": 1}, "text": "hello"}})
        self.assertEqual(response.status_code, 404)

    def test_creates_intake_buffer_for_valid_message(self):
        response = self._post(
            {
                "message": {
                    "chat": {"id": 42},
                    "message_id": 99,
                    "date": 1700000000,
                    "text": "hello world",
                }
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

        buffer = IntakeBuffer.objects.get()
        self.assertEqual(buffer.bot, self.bot)
        self.assertEqual(buffer.chat_id, "42")
        self.assertEqual(buffer.reply_to_message_id, 99)
        self.assertEqual(buffer.text, "hello world")
        self.assertEqual(buffer.last_message_ts, 1700000000)
        self.assertIsNotNone(buffer.last_received_at)
        self.assertIsNone(buffer.flushed_at)
        self.assertFalse(Job.objects.exists())

    def test_merges_consecutive_messages_into_one_buffer(self):
        self._post(
            {
                "message": {
                    "chat": {"id": 7},
                    "message_id": 10,
                    "date": 1700000000,
                    "text": "first",
                }
            }
        )
        self._post(
            {
                "message": {
                    "chat": {"id": 7},
                    "message_id": 11,
                    "date": 1700000005,
                    "text": "second",
                }
            }
        )

        self.assertEqual(IntakeBuffer.objects.count(), 1)
        buffer = IntakeBuffer.objects.get()
        self.assertEqual(buffer.text, "first\nsecond")
        self.assertEqual(buffer.message_count, 2)
        self.assertEqual(buffer.reply_to_message_id, 10)
        self.assertEqual(buffer.last_message_ts, 1700000005)
        self.assertIsNone(buffer.flushed_at)
        self.assertFalse(Job.objects.exists())

    def test_message_beyond_interval_creates_job(self):
        self._post(
            {
                "message": {
                    "chat": {"id": 7},
                    "message_id": 10,
                    "date": 1700000000,
                    "text": "first",
                }
            }
        )
        self._post(
            {
                "message": {
                    "chat": {"id": 7},
                    "message_id": 11,
                    "date": 1700000020,
                    "text": "second",
                }
            }
        )

        self.assertEqual(
            IntakeBuffer.objects.filter(flushed_at__isnull=False).count(), 1
        )
        self.assertEqual(
            IntakeBuffer.objects.filter(flushed_at__isnull=True).count(), 1
        )
        flushed = IntakeBuffer.objects.get(flushed_at__isnull=False)
        self.assertEqual(flushed.text, "first")
        self.assertEqual(flushed.reply_to_message_id, 10)
        job = Job.objects.get()
        self.assertEqual(job.raw_input, "first")
        self.assertEqual(job.reply_to_message_id, 10)
        open_buffer = IntakeBuffer.objects.get(flushed_at__isnull=True)
        self.assertEqual(open_buffer.text, "second")
        self.assertEqual(open_buffer.last_message_ts, 1700000020)
