from django.test import TestCase

from engine.telegram.models import Bot, generate_webhook_secret


class BotModelTests(TestCase):
    def test_bot_string_is_name(self):
        bot = Bot.objects.create(
            name="bot-name",
            telegram_api_token="telegram-token",
        )
        self.assertEqual(str(bot), "bot-name")

    def test_webhook_secret_generated_on_create(self):
        bot = Bot.objects.create(
            name="secret-bot",
            telegram_api_token="telegram-token",
        )
        self.assertEqual(len(bot.webhook_secret), 32)
        self.assertTrue(bot.webhook_secret.isalnum())

    def test_rotate_webhook_secret_updates_db(self):
        bot = Bot.objects.create(
            name="rotate-bot",
            telegram_api_token="telegram-token",
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
