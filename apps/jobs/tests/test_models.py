from django.test import TestCase

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.models import Job
from apps.library.models import Skill, Wrapper


class JobModelTests(TestCase):
    def test_job_string_includes_id_and_bot_name(self):
        skill = Skill.objects.create(name="s", content="s")
        wrapper = Wrapper.objects.create(name="w", skill=skill, content="w")
        provider = Provider.objects.create(
            name="p",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(provider=provider, name="pr", model="gpt-4o")
        bot = Bot.objects.create(
            name="bot-name",
            telegram_api_token="telegram-token",
            profile=profile,
            wrapper=wrapper,
        )
        job = Job.objects.create(
            bot=bot,
            reply_target="123",
            raw_input="hello",
        )

        self.assertEqual(str(job), f"Job #{job.pk} [bot-name]")
