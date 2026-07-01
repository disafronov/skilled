from unittest.mock import MagicMock, patch

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

    def test_job_admin_exposes_retry_actions(self):
        admin = JobAdmin(Job, AdminSite())

        self.assertIn("retry_llm_jobs", admin.get_actions(MagicMock()))
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
                "llm_started_at",
                "llm_finished_at",
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
                            "llm_started_at",
                            "llm_finished_at",
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
                "llm_started_at",
                "llm_finished_at",
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

    @patch("apps.jobs.admin.async_task")
    def test_retry_llm_jobs_resets_and_requeues(self, mock_async):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()
        admin.message_user = MagicMock()
        job = Job.objects.create(
            bot=self.job.bot,
            reply_target="retry-llm",
            raw_input="hello",
            llm_started_at=self.job.created_at,
            error="llm down",
        )

        admin.retry_llm_jobs(request, Job.objects.filter(pk=job.pk))

        job.refresh_from_db()
        self.assertIsNone(job.llm_started_at)
        self.assertIsNone(job.llm_finished_at)
        self.assertIsNone(job.raw_output)
        self.assertIsNone(job.error)
        self.assertIsNone(job.delivery_started_at)
        self.assertIsNone(job.delivery_finished_at)
        mock_async.assert_called_once_with("apps.jobs.tasks.llm_worker", job.pk)
        admin.message_user.assert_called_once()

    @patch("apps.jobs.admin.async_task")
    def test_retry_llm_jobs_resets_completed_job(self, mock_async):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()
        admin.message_user = MagicMock()
        job = Job.objects.create(
            bot=self.job.bot,
            reply_target="done",
            raw_input="hello",
            llm_started_at=self.job.created_at,
            llm_finished_at=self.job.created_at,
            raw_output="response",
            delivery_started_at=self.job.created_at,
            delivery_finished_at=self.job.created_at,
        )

        admin.retry_llm_jobs(request, Job.objects.filter(pk=job.pk))

        job.refresh_from_db()
        self.assertIsNone(job.llm_started_at)
        self.assertIsNone(job.llm_finished_at)
        self.assertIsNone(job.raw_output)
        self.assertIsNone(job.error)
        self.assertIsNone(job.delivery_started_at)
        self.assertIsNone(job.delivery_finished_at)
        mock_async.assert_called_once_with("apps.jobs.tasks.llm_worker", job.pk)

    @patch("apps.jobs.admin.async_task")
    def test_retry_delivery_jobs_resets_and_requeues(self, mock_async):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()
        admin.message_user = MagicMock()
        job = Job.objects.create(
            bot=self.job.bot,
            reply_target="retry-delivery",
            raw_input="hello",
            llm_started_at=self.job.created_at,
            llm_finished_at=self.job.created_at,
            raw_output="response",
            delivery_started_at=self.job.created_at,
            error="telegram down",
        )

        admin.retry_delivery_jobs(request, Job.objects.filter(pk=job.pk))

        job.refresh_from_db()
        self.assertIsNotNone(job.llm_finished_at)
        self.assertEqual(job.raw_output, "response")
        self.assertIsNone(job.delivery_started_at)
        self.assertIsNone(job.delivery_finished_at)
        self.assertIsNone(job.error)
        mock_async.assert_called_once_with("apps.jobs.tasks.telegram_deliver", job.pk)
        admin.message_user.assert_called_once()

    @patch("apps.jobs.admin.async_task")
    def test_retry_delivery_jobs_resets_completed_delivery(self, mock_async):
        admin = JobAdmin(Job, AdminSite())
        request = MagicMock()
        admin.message_user = MagicMock()
        job = Job.objects.create(
            bot=self.job.bot,
            reply_target="done-delivery",
            raw_input="hello",
            llm_started_at=self.job.created_at,
            llm_finished_at=self.job.created_at,
            raw_output="response",
            delivery_started_at=self.job.created_at,
            delivery_finished_at=self.job.created_at,
        )

        admin.retry_delivery_jobs(request, Job.objects.filter(pk=job.pk))

        job.refresh_from_db()
        self.assertIsNotNone(job.llm_finished_at)
        self.assertEqual(job.raw_output, "response")
        self.assertIsNone(job.delivery_started_at)
        self.assertIsNone(job.delivery_finished_at)
        self.assertIsNone(job.error)
        mock_async.assert_called_once_with("apps.jobs.tasks.telegram_deliver", job.pk)
