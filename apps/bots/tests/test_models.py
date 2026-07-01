from django.test import TestCase

from apps.bots.models import Bot, generate_webhook_secret
from apps.inference.models import Profile, Provider
from apps.library.models import Skill, Wrapper


class BotModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        skill = Skill.objects.create(name="s", content="s")
        cls.wrapper = Wrapper.objects.create(name="w", skill=skill, content="w")
        provider = Provider.objects.create(
            name="p",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        cls.profile = Profile.objects.create(
            provider=provider, name="pr", model="gpt-4o"
        )

    def test_bot_string_is_name(self):
        bot = Bot.objects.create(
            name="bot-name",
            telegram_api_token="telegram-token",
            profile=self.profile,
            wrapper=self.wrapper,
        )
        self.assertEqual(str(bot), "bot-name")

    def test_webhook_secret_generated_on_create(self):
        bot = Bot.objects.create(
            name="secret-bot",
            telegram_api_token="telegram-token",
            profile=self.profile,
            wrapper=self.wrapper,
        )
        self.assertEqual(len(bot.webhook_secret), 32)
        self.assertTrue(bot.webhook_secret.isalnum())

    def test_rotate_webhook_secret_updates_db(self):
        bot = Bot.objects.create(
            name="rotate-bot",
            telegram_api_token="telegram-token",
            profile=self.profile,
            wrapper=self.wrapper,
        )
        original_secret = bot.webhook_secret
        bot.webhook_enabled_at = None

        bot.rotate_webhook_secret()
        bot.refresh_from_db()

        self.assertNotEqual(bot.webhook_secret, original_secret)
        self.assertIsNone(bot.webhook_enabled_at)

    def test_generate_webhook_secret_returns_32_hex_chars(self):
        secret = generate_webhook_secret()
        self.assertEqual(len(secret), 32)
        # hex chars = 0-9, a-f only
        int(secret, 16)
