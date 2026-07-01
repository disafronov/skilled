"""Tests for bot webhook views."""

import json
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.models import Job
from apps.library.models import Skill, Wrapper


class WebhookViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.raw_token = "123456:ABC-DEF1234abcdef"
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
            provider=provider, name="webhook-profile", model="gpt-4o"
        )
        cls.bot = Bot.objects.create(
            name="webhook-bot",
            telegram_api_token=cls.raw_token,
            profile=profile,
            wrapper=wrapper,
        )

    def _url(self, token: str | None = None) -> str:
        return reverse("webhook", kwargs={"token": token or self.raw_token})

    def _post(self, data: dict, token: str | None = None):
        return self.client.post(
            self._url(token),
            data=json.dumps(data),
            content_type="application/json",
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

    def test_returns_404_for_unknown_token(self):
        response = self._post(
            {"message": {"chat": {"id": 1}, "text": "hello"}},
            token="unknown:token",
        )
        self.assertEqual(response.status_code, 404)

    def test_returns_404_when_bot_disabled(self):
        self.bot.enabled = False
        self.bot.save(update_fields=["enabled"])

        response = self._post({"message": {"chat": {"id": 1}, "text": "hello"}})
        self.assertEqual(response.status_code, 404)

    def test_returns_500_on_encryption_key_missing(self):
        from apps.common.fields import _cipher

        _cipher.cache_clear()
        with patch.dict("os.environ", {"FIELD_ENCRYPTION_KEY": ""}):
            response = self._post({"message": {"chat": {"id": 1}, "text": "hello"}})
        _cipher.cache_clear()

        self.assertEqual(response.status_code, 500)

    def test_creates_job_for_valid_message(self):
        response = self._post(
            {
                "message": {
                    "chat": {"id": 42},
                    "message_id": 99,
                    "text": "hello world",
                }
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

        job = Job.objects.get()
        self.assertEqual(job.bot, self.bot)
        self.assertEqual(job.reply_target, "42")
        self.assertEqual(job.reply_to_message_id, 99)
        self.assertEqual(job.raw_input, "hello world")
