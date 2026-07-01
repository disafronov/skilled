from django.test import TestCase
from django.utils import timezone

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.models import IntakeBuffer, Job, Worker
from apps.library.models import Skill, Wrapper


class JobModelTests(TestCase):
    def test_job_string_includes_id_and_bot_name(self):
        bot = Bot.objects.create(
            name="bot-name",
            telegram_api_token="telegram-token",
        )
        job = Job.objects.create(
            bot=bot,
            reply_target="123",
            raw_input="hello",
        )

        self.assertEqual(str(job), f"Job #{job.pk} [bot-name]")


class IntakeBufferModelTests(TestCase):
    def test_buffer_string_includes_id_bot_and_chat(self):
        bot = Bot.objects.create(
            name="buffer-bot",
            telegram_api_token="tok",
        )
        buffer = IntakeBuffer.objects.create(
            bot=bot,
            chat_id="42",
            text="hello",
            last_message_ts=1700000000,
            last_received_at=timezone.now(),
        )
        self.assertEqual(str(buffer), f"IntakeBuffer #{buffer.pk} [buffer-bot] #42")


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
