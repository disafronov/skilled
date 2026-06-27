from unittest.mock import MagicMock

from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.admin import JOB_PREVIEW_LENGTH, JobAdmin, preview_text
from apps.jobs.models import Job
from apps.library.models import Skill, Wrapper


class JobAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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
            name="b",
            telegram_api_token="telegram-token",
            profile=profile,
            wrapper=wrapper,
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
                "llm_started_at",
                "llm_finished_at",
                "sent_at",
                "updated_at",
            ),
        )
        self.assertEqual(
            admin.fields,
            (
                "id",
                "bot",
                "reply_target",
                "reply_to_message_id",
                "raw_input",
                "raw_output",
                "error",
                "llm_started_at",
                "llm_finished_at",
                "sent_at",
                "updated_at",
                "created_at",
            ),
        )
        self.assertEqual(admin.readonly_fields, admin.fields)
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
