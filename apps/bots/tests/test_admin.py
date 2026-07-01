from unittest.mock import MagicMock, Mock

from django import forms
from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase, TestCase

from apps.bots.admin import BotAdmin
from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.library.models import Skill, Wrapper


class BotAdminTests(SimpleTestCase):
    def test_bot_admin_order_comes_from_model(self):
        admin = BotAdmin(Bot, AdminSite())

        self.assertEqual(
            admin.fieldsets,
            (
                (
                    None,
                    {
                        "fields": (
                            "name",
                            "telegram_api_token",
                            "profile",
                            "wrapper",
                            "enabled",
                            "telegram_update_offset",
                        )
                    },
                ),
                (
                    "Webhook",
                    {
                        "fields": (
                            "webhook_enabled_at",
                            "webhook_disabled_at",
                        )
                    },
                ),
                ("Changes", {"fields": ("updated_at", "created_at")}),
            ),
        )
        self.assertEqual(
            admin.readonly_fields,
            ("webhook_enabled_at", "webhook_disabled_at", "updated_at", "created_at"),
        )
        self.assertEqual(
            admin.list_display,
            (
                "name",
                "profile",
                "wrapper",
                "enabled",
                "telegram_update_offset",
                "webhook_enabled_at",
                "webhook_disabled_at",
                "updated_at",
            ),
        )

    def test_bot_form_orders_name_first_and_uses_acronym_label(self):
        admin = BotAdmin(Bot, AdminSite())
        form_class = admin.get_form(MagicMock())
        form = form_class()

        self.assertEqual(
            list(form.fields),
            [
                "name",
                "telegram_api_token",
                "profile",
                "wrapper",
                "enabled",
                "telegram_update_offset",
            ],
        )
        self.assertEqual(
            form.fields["telegram_api_token"].label,
            "Telegram API credential",
        )
        self.assertEqual(
            form.fields["name"].widget.attrs["style"],
            "width: 32rem; max-width: 100%;",
        )
        self.assertNotIn("style", form.fields["enabled"].widget.attrs)

    def test_telegram_api_token_uses_non_rendering_password_widget(self):
        bot = Bot(
            name="bot",
            telegram_api_token="telegram-token",
        )
        bot.pk = 1  # simulate existing DB instance
        admin = BotAdmin(Bot, AdminSite())
        form_class = admin.get_form(MagicMock(), bot)
        form = form_class(instance=bot)
        widget = form.fields["telegram_api_token"].widget

        self.assertIsInstance(widget, forms.PasswordInput)
        self.assertFalse(widget.render_value)
        self.assertFalse(form.fields["telegram_api_token"].required)
        self.assertEqual(
            widget.attrs["placeholder"],
            "Already set. Enter a new value to replace it.",
        )
        self.assertEqual(form.fields["telegram_api_token"].help_text, "")
        self.assertNotIn(
            "telegram-token",
            widget.render("telegram_api_token", bot.telegram_api_token),
        )

    def test_telegram_api_token_keeps_existing_value_when_left_empty(self):
        bot = Bot(
            name="bot",
            telegram_api_token="telegram-token",
        )
        bot.pk = 1  # simulate existing DB instance
        admin = BotAdmin(Bot, AdminSite())
        form_class = admin.get_form(MagicMock(), bot)
        form = form_class(instance=bot)
        form.cleaned_data = {"telegram_api_token": ""}

        cleaned = form.clean()
        self.assertNotIn("telegram_api_token", cleaned)


class BotAdminActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(name="s", content="s")
        cls.wrapper = Wrapper.objects.create(name="w", skill=cls.skill, content="w")
        cls.provider = Provider.objects.create(
            name="p",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        cls.profile = Profile.objects.create(
            provider=cls.provider, name="pr", model="gpt-4o"
        )

    def test_rotate_webhook_secret_action_executes(self):
        bot = Bot.objects.create(
            name="action-bot",
            telegram_api_token="telegram-token",
            profile=self.profile,
            wrapper=self.wrapper,
        )
        original_secret = bot.webhook_secret
        admin = BotAdmin(Bot, AdminSite())
        request = Mock()

        admin.rotate_webhook_secret(request, Bot.objects.filter(pk=bot.pk))

        bot.refresh_from_db()
        self.assertNotEqual(bot.webhook_secret, original_secret)
        self.assertIsNone(bot.webhook_enabled_at)
        request.method  # verify Mock used correctly
