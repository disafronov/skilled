from unittest.mock import MagicMock, Mock, patch

from django import forms
from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase, TestCase

from engine.telegram.admin import (
    JOB_PREVIEW_LENGTH,
    BotAdmin,
    JobAdmin,
    preview_text,
)
from engine.telegram.models import Bot, Job


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
    def test_rotate_webhook_secret_action_executes(self):
        bot = Bot.objects.create(
            name="action-bot",
            telegram_api_token="telegram-token",
        )
        original_secret = bot.webhook_secret
        admin = BotAdmin(Bot, AdminSite())
        request = Mock()

        admin.rotate_webhook_secret(request, Bot.objects.filter(pk=bot.pk))

        bot.refresh_from_db()
        self.assertNotEqual(bot.webhook_secret, original_secret)
        self.assertIsNone(bot.webhook_enabled_at)
        request.method  # verify Mock used correctly


class MaskedFieldAdminFormTests(TestCase):
    """AdminModelForm must never decrypt masked fields to check or preserve values."""

    def test_bot_admin_form_skips_empty_masked_field_for_existing_instance(self):
        bot = Bot.objects.create(
            name="bot",
            telegram_api_token="telegram-token",
        )

        from engine.telegram.admin import BotAdminForm

        form = BotAdminForm(
            data={
                "name": "bot",
                "telegram_api_token": "",
                "enabled": True,
                "telegram_update_offset": 0,
            },
            instance=bot,
        )

        self.assertTrue(form.is_valid())
        self.assertNotIn("telegram_api_token", form.cleaned_data)

    def test_bot_admin_form_masked_field_required_for_new_instance(self):
        from engine.telegram.admin import BotAdminForm

        form = BotAdminForm(
            data={
                "name": "new-bot",
                "telegram_api_token": "",
                "enabled": True,
                "telegram_update_offset": 0,
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("telegram_api_token", form.errors)

    def test_bot_admin_form_new_value_in_masked_field_used(self):
        bot = Bot.objects.create(
            name="bot",
            telegram_api_token="old-token",
        )

        from engine.telegram.admin import BotAdminForm

        form = BotAdminForm(
            data={
                "name": "bot",
                "telegram_api_token": "new-token",
                "enabled": True,
                "telegram_update_offset": 0,
            },
            instance=bot,
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["telegram_api_token"], "new-token")


class PreviewTextTests(SimpleTestCase):
    """preview_text utility function."""

    def test_truncates_long_values(self):
        long_text = "x" * (JOB_PREVIEW_LENGTH + 20)
        preview = preview_text(long_text)

        self.assertLess(len(preview), len(long_text))
        self.assertTrue(preview.startswith("x" * (JOB_PREVIEW_LENGTH - 4)))

    def test_returns_empty_for_none(self):
        self.assertEqual(preview_text(None), "")

    def test_returns_empty_for_empty_string(self):
        self.assertEqual(preview_text(""), "")

    def test_short_value_unchanged(self):
        self.assertEqual(preview_text("hello"), "hello")

    def test_exact_length_value(self):
        text = "x" * JOB_PREVIEW_LENGTH
        self.assertEqual(preview_text(text), text)


class JobAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        bot = Bot.objects.create(
            name="b",
            telegram_api_token="telegram-token",
        )
        cls.job = Job.objects.create(
            bot=bot,
            reply_target="123",
            raw_input="hello",
        )

    def test_job_admin_is_read_only(self):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()

        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request, self.job))
        self.assertFalse(admin.has_delete_permission(request, self.job))

    def test_job_admin_exposes_retry_actions(self):
        admin = JobAdmin(Job, AdminSite())

        self.assertIn("retry_jobs", admin.get_actions(MagicMock()))
        self.assertIn("retry_delivery_jobs", admin.get_actions(MagicMock()))

    def test_job_admin_order_comes_from_model(self):
        admin = JobAdmin(Job, AdminSite())

        self.assertEqual(
            admin.list_display,
            (
                "id",
                "bot",
                "reply_target",
                "reply_to_message_id",
                "raw_input_preview",
                "raw_output_preview",
                "error_preview",
                "processing_started_at",
                "processing_finished_at",
                "delivery_started_at",
                "delivery_finished_at",
                "updated_at",
            ),
        )
        self.assertEqual(
            admin.fieldsets,
            (
                (
                    None,
                    {
                        "fields": (
                            "id",
                            "bot",
                            "reply_target",
                            "reply_to_message_id",
                            "raw_input",
                            "raw_output",
                            "error",
                        )
                    },
                ),
                (
                    "Pipeline",
                    {
                        "fields": (
                            "processing_started_at",
                            "processing_finished_at",
                            "delivery_started_at",
                            "delivery_finished_at",
                        )
                    },
                ),
                ("Changes", {"fields": ("updated_at", "created_at")}),
            ),
        )
        self.assertEqual(
            admin.readonly_fields,
            (
                "id",
                "bot",
                "reply_target",
                "reply_to_message_id",
                "raw_input",
                "raw_output",
                "error",
                "processing_started_at",
                "processing_finished_at",
                "delivery_started_at",
                "delivery_finished_at",
                "updated_at",
                "created_at",
            ),
        )
        self.assertNotIn("raw_input", admin.list_display)
        self.assertNotIn("raw_output", admin.list_display)
        self.assertNotIn("error", admin.list_display)

    def test_job_admin_text_preview_truncates_long_values(self):
        long_text = "x" * (JOB_PREVIEW_LENGTH + 20)
        preview = preview_text(long_text)

        self.assertLess(len(preview), len(long_text))
        self.assertTrue(preview.startswith("x" * (JOB_PREVIEW_LENGTH - 4)))

    def test_job_admin_preview_methods_handle_empty_values(self):
        admin = JobAdmin(Job, AdminSite())

        self.assertEqual(admin.raw_output_preview(self.job), "")
        self.assertEqual(admin.error_preview(self.job), "")

    def test_job_admin_preview_methods_use_common_truncation(self):
        admin = JobAdmin(Job, AdminSite())
        self.job.raw_input = "x" * (JOB_PREVIEW_LENGTH + 20)

        self.assertEqual(
            admin.raw_input_preview(self.job), preview_text(self.job.raw_input)
        )

    @patch("engine.telegram.admin.async_task")
    def test_retry_jobs_resets_and_requeues(self, mock_async):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()
        admin.message_user = MagicMock()
        job = Job.objects.create(
            bot=self.job.bot,
            reply_target="retry-job",
            raw_input="hello",
            processing_started_at=self.job.created_at,
            error="processing down",
        )

        admin.retry_jobs(request, Job.objects.filter(pk=job.pk))

        job.refresh_from_db()
        self.assertIsNone(job.processing_started_at)
        self.assertIsNone(job.processing_finished_at)
        self.assertIsNone(job.raw_output)
        self.assertIsNone(job.error)
        self.assertIsNone(job.delivery_started_at)
        self.assertIsNone(job.delivery_finished_at)
        mock_async.assert_called_once_with("engine.processing.proxy.worker", job.pk)

    @patch("engine.telegram.admin.async_task")
    def test_retry_delivery_jobs_resets_and_requeues(self, mock_async):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()
        admin.message_user = MagicMock()
        job = Job.objects.create(
            bot=self.job.bot,
            reply_target="retry-delivery",
            raw_input="hello",
            raw_output="some result",
            processing_finished_at=self.job.created_at,
            delivery_started_at=self.job.created_at,
            error="delivery failed",
        )

        admin.retry_delivery_jobs(request, Job.objects.filter(pk=job.pk))

        job.refresh_from_db()
        self.assertIsNone(job.delivery_started_at)
        self.assertIsNone(job.delivery_finished_at)
        self.assertIsNone(job.error)
        mock_async.assert_called_once_with(
            "engine.telegram.tasks.telegram_deliver", job.pk
        )

    def test_job_str(self):
        self.assertIn(str(self.job.pk), str(self.job))
        self.assertIn(self.job.bot.name, str(self.job))

    def test_intake_buffer_str(self):
        from django.utils import timezone

        from engine.telegram.models import IntakeBuffer

        ts = int(timezone.now().timestamp())
        buffer = IntakeBuffer.objects.create(
            bot=self.job.bot,
            chat_id=100500,
            message_count=1,
            text="hello",
            last_message_ts=ts,
            last_received_at=timezone.now(),
        )
        self.assertIn(str(buffer.pk), str(buffer))
        self.assertIn(str(100500), str(buffer))
        self.assertIn(self.job.bot.name, str(buffer))
