"""Worker model tests — moved from engine/jobs/tests/test_models.py."""

from django.test import TestCase

from apps.inference.models import Profile, Provider
from apps.library.models import Skill, Wrapper
from apps.llm.models import Worker
from engine.telegram.models import Bot


class WorkerModelTests(TestCase):
    def test_worker_string_is_worker_for_bot(self):
        skill = Skill.objects.create(name="ws", content="ws")
        wrapper = Wrapper.objects.create(name="ww", skill=skill, content="ww")
        provider = Provider.objects.create(
            name="wp",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(provider=provider, name="wpr", model="gpt-4o")
        bot = Bot.objects.create(
            name="worker-bot",
            telegram_api_token="tok",
        )
        worker = Worker.objects.create(
            bot=bot,
            profile=profile,
            wrapper=wrapper,
        )
        self.assertEqual(str(worker), f"Worker for {bot.name}")
