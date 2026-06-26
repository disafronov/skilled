from django.test import TestCase

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.library.models import Skill, Wrapper


class BotModelTests(TestCase):
    def test_bot_string_is_name(self):
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

        self.assertEqual(str(bot), "bot-name")
