from unittest.mock import patch

from django.test import TestCase

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.models import Job
from apps.library.models import Skill, Wrapper


class SignalOrchestrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        skill = Skill.objects.create(name="sig-skill", content="s")
        wrapper = Wrapper.objects.create(name="sig-wrapper", skill=skill, content="w")
        provider = Provider.objects.create(
            name="sig-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(
            provider=provider, name="sig-pr", model="gpt-4o"
        )
        cls.bot = Bot.objects.create(
            name="sig-bot",
            telegram_api_token="telegram-token",
            profile=profile,
            wrapper=wrapper,
        )

    @patch("apps.jobs.signals.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.jobs.signals.async_task")
    def test_created_schedules_llm_worker(self, mock_async_task, mock_on_commit):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        mock_async_task.assert_called_once_with("apps.jobs.tasks.llm_worker", job.pk)

    @patch("apps.jobs.signals.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.jobs.signals.async_task")
    def test_llm_finished_schedules_delivery(self, mock_async_task, mock_on_commit):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        mock_async_task.reset_mock()

        job.raw_output = "some output"
        job.llm_finished_at = job.created_at
        job.save(update_fields=["raw_output", "llm_finished_at"])

        mock_async_task.assert_called_once_with(
            "apps.jobs.tasks.telegram_deliver", job.pk
        )

    @patch("apps.jobs.signals.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("apps.jobs.signals.async_task")
    def test_other_update_does_not_schedule(self, mock_async_task, mock_on_commit):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        mock_async_task.reset_mock()

        job.reply_target = "456"
        job.save(update_fields=["reply_target"])

        mock_async_task.assert_not_called()
