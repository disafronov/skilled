from datetime import datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django_q.models import Schedule

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.models import Job
from apps.jobs.apps import create_schedules
from apps.jobs.tasks import QUEUE_ACK_TEXT, telegram_deliver, telegram_ingest
from apps.library.models import Skill, Wrapper
from workers.llm import build_request_body
from workers.telegram import TELEGRAM_MESSAGE_CHAR_LIMIT


class JobSelectionPredicatesTests(TestCase):
    """Test that job selection queries correctly identify pending jobs."""

    @classmethod
    def setUpTestData(cls):
        now = datetime.now(dt_timezone.utc)
        skill = Skill.objects.create(name="s", content="s")
        wrapper = Wrapper.objects.create(name="w", content="w")
        provider = Provider.objects.create(
            name="p",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(name="pr", model="gpt-4o")
        bot = Bot.objects.create(
            name="b",
            telegram_api_token="tok",
            provider=provider,
            profile=profile,
            skill=skill,
            wrapper=wrapper,
        )

        # Pending job: received, not started, no error
        cls.pending = Job.objects.create(
            bot=bot,
            reply_target="1",
            raw_input="hi",
            received_at=now,
        )

        # In progress: llm_started_at is set
        cls.in_progress = Job.objects.create(
            bot=bot,
            reply_target="2",
            raw_input="hi2",
            received_at=now,
            llm_started_at=now,
        )

        # Completed: llm_finished_at set, raw_output set, no error
        cls.completed = Job.objects.create(
            bot=bot,
            reply_target="3",
            raw_input="hi3",
            raw_output="some response",
            received_at=now,
            llm_started_at=now,
            llm_finished_at=now,
        )

        # Failed: has error
        cls.failed = Job.objects.create(
            bot=bot,
            reply_target="4",
            raw_input="hi4",
            received_at=now,
            error="something went wrong",
        )

    def test_pending_job_selected(self):
        """Pending job (received, not started, no error) should match."""
        qs = Job.objects.filter(
            received_at__isnull=False,
            llm_started_at__isnull=True,
            error__isnull=True,
        )
        self.assertIn(self.pending, qs)
        self.assertNotIn(self.in_progress, qs)
        self.assertNotIn(self.completed, qs)
        self.assertNotIn(self.failed, qs)

    def test_deliverable_job_selected(self):
        """Deliverable: llm_finished_at set, raw_output set, sent_at null, no error."""
        qs = Job.objects.filter(
            llm_finished_at__isnull=False,
            raw_output__isnull=False,
            sent_at__isnull=True,
            error__isnull=True,
        )
        self.assertIn(self.completed, qs)
        self.assertNotIn(self.pending, qs)
        self.assertNotIn(self.in_progress, qs)
        self.assertNotIn(self.failed, qs)


class DerivedJobStatesTests(TestCase):
    """Test that job state is correctly derived from timestamps and error."""

    @classmethod
    def setUpTestData(cls):
        now = datetime.now(dt_timezone.utc)
        skill = Skill.objects.create(name="s", content="s")
        wrapper = Wrapper.objects.create(name="w", content="w")
        provider = Provider.objects.create(
            name="p",
            api_type="openai",
            base_url="https://x.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(name="pr", model="gpt-4o")
        bot = Bot.objects.create(
            name="b",
            telegram_api_token="tok",
            provider=provider,
            profile=profile,
            skill=skill,
            wrapper=wrapper,
        )

        cls.pending = Job.objects.create(
            bot=bot,
            reply_target="1",
            raw_input="hi",
            received_at=now,
        )
        cls.processing = Job.objects.create(
            bot=bot,
            reply_target="2",
            raw_input="hi2",
            received_at=now,
            llm_started_at=now,
        )
        cls.done = Job.objects.create(
            bot=bot,
            reply_target="3",
            raw_input="hi3",
            received_at=now,
            llm_started_at=now,
            llm_finished_at=now,
            raw_output="resp",
        )
        cls.failed = Job.objects.create(
            bot=bot,
            reply_target="4",
            raw_input="hi4",
            received_at=now,
            llm_started_at=now,
            llm_finished_at=now,
            error="fail",
        )

    def assert_state(self, job, pending, processing, completed, failed):
        self.assertEqual(
            job.received_at is not None
            and job.llm_started_at is None
            and job.error is None,
            pending,
        )
        self.assertEqual(
            job.llm_started_at is not None
            and job.llm_finished_at is None
            and job.error is None,
            processing,
        )
        self.assertEqual(
            job.llm_finished_at is not None
            and job.raw_output is not None
            and job.error is None,
            completed,
        )
        self.assertEqual(
            job.error is not None,
            failed,
        )

    def test_pending_state(self):
        self.assert_state(self.pending, True, False, False, False)

    def test_processing_state(self):
        self.assert_state(self.processing, False, True, False, False)

    def test_completed_state(self):
        self.assert_state(self.done, False, False, True, False)

    def test_failed_state(self):
        self.assert_state(self.failed, False, False, False, True)


class OpenAiRequestAssemblyTests(TestCase):
    """Test that build_request_body produces correct OpenAI-compatible bodies."""

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(
            name="translate", content="Translate to French."
        )
        cls.wrapper = Wrapper.objects.create(
            name="strict",
            content="Respond in JSON format.",
        )
        cls.profile = Profile.objects.create(
            name="default",
            model="gpt-4o",
            temperature=0.7,
            top_p=None,
            max_output_tokens=500,
            reasoning_effort=None,
            response_format=None,
        )

    def test_basic_request_body(self):
        body = build_request_body(self.profile, self.skill, self.wrapper, "hello", "")
        self.assertEqual(body["model"], "gpt-4o")
        self.assertEqual(len(body["messages"]), 2)
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertIn("Translate to French.", body["messages"][0]["content"])
        self.assertIn("Respond in JSON format.", body["messages"][0]["content"])
        self.assertEqual(body["messages"][1]["role"], "user")
        self.assertEqual(body["messages"][1]["content"], "hello")

    def test_temperature_included(self):
        body = build_request_body(self.profile, self.skill, self.wrapper, "hello", "")
        self.assertEqual(body["temperature"], 0.7)

    def test_max_tokens_mapped(self):
        body = build_request_body(self.profile, self.skill, self.wrapper, "hello", "")
        self.assertEqual(body["max_completion_tokens"], 500)

    def test_global_system_prompt_appended(self):
        body = build_request_body(
            self.profile,
            self.skill,
            self.wrapper,
            "hello",
            "You are a helpful assistant.",
        )
        system_content = body["messages"][0]["content"]
        self.assertIn("You are a helpful assistant.", system_content)


class NullableProfileFieldOmissionTests(TestCase):
    """Test that null profile fields are omitted from the request body."""

    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(name="s", content="s")
        cls.wrapper = Wrapper.objects.create(name="w", content="w")
        cls.profile_all_null = Profile.objects.create(
            name="minimal",
            model="gpt-4o",
            temperature=None,
            top_p=None,
            max_output_tokens=None,
            reasoning_effort=None,
            response_format=None,
        )

    def test_only_model_and_messages(self):
        body = build_request_body(
            self.profile_all_null,
            self.skill,
            self.wrapper,
            "hello",
            "",
        )
        self.assertEqual(body["model"], "gpt-4o")
        self.assertIn("messages", body)
        self.assertNotIn("temperature", body)
        self.assertNotIn("top_p", body)
        self.assertNotIn("max_tokens", body)
        self.assertNotIn("reasoning_effort", body)
        self.assertNotIn("response_format", body)


class Q2ScheduleTests(TestCase):
    """Test the pipeline schedule configuration."""

    def test_default_schedules_use_standard_five_field_cron(self):
        create_schedules(sender=None)

        schedules = {
            schedule.name: schedule
            for schedule in Schedule.objects.filter(
                name__in=["telegram_ingest", "llm_worker", "telegram_deliver"]
            )
        }

        self.assertEqual(schedules["telegram_ingest"].schedule_type, Schedule.CRON)
        self.assertEqual(schedules["telegram_ingest"].cron, "* * * * *")
        self.assertEqual(schedules["llm_worker"].schedule_type, Schedule.CRON)
        self.assertEqual(schedules["llm_worker"].cron, "* * * * *")
        self.assertEqual(schedules["telegram_deliver"].schedule_type, Schedule.CRON)
        self.assertEqual(schedules["telegram_deliver"].cron, "* * * * *")


class TelegramDeliveryTests(TestCase):
    """Test Telegram delivery method selection."""

    @classmethod
    def setUpTestData(cls):
        cls.now = datetime.now(dt_timezone.utc)
        skill = Skill.objects.create(name="delivery-skill", content="s")
        wrapper = Wrapper.objects.create(name="delivery-wrapper", content="w")
        provider = Provider.objects.create(
            name="delivery-provider",
            api_type="openai",
            base_url="https://example.com",
            auth_token="tok",
        )
        profile = Profile.objects.create(name="delivery-profile", model="gpt-4o")
        cls.bot = Bot.objects.create(
            name="delivery-bot",
            telegram_api_token="telegram-token",
            provider=provider,
            profile=profile,
            skill=skill,
            wrapper=wrapper,
        )

    @patch("apps.jobs.tasks.send_document")
    @patch("apps.jobs.tasks.send_message")
    def test_short_response_sent_as_message(self, send_message, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output="short response",
            received_at=self.now,
            llm_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_called_once_with(
            "telegram-token",
            "123",
            "short response",
            reply_to_message_id=456,
        )
        send_document.assert_not_called()
        job.refresh_from_db()
        self.assertIsNotNone(job.sent_at)
        self.assertIsNone(job.error)

    @patch("apps.jobs.tasks.send_message")
    @patch("apps.jobs.tasks.get_updates")
    def test_ingest_stores_reply_message_id(self, get_updates, send_message):
        get_updates.return_value = [
            {
                "update_id": 100,
                "message": {
                    "message_id": 456,
                    "chat": {"id": 123},
                    "text": "hello",
                },
            }
        ]

        telegram_ingest()

        job = Job.objects.get(raw_input="hello")
        self.assertEqual(job.reply_target, "123")
        self.assertEqual(job.reply_to_message_id, 456)
        send_message.assert_called_once_with(
            "telegram-token",
            "123",
            QUEUE_ACK_TEXT,
            reply_to_message_id=456,
        )

    @patch("apps.jobs.tasks.send_document")
    @patch("apps.jobs.tasks.send_message")
    def test_long_response_sent_as_document(self, send_message, send_document):
        output = "x" * (TELEGRAM_MESSAGE_CHAR_LIMIT + 1)
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output=output,
            received_at=self.now,
            llm_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_not_called()
        send_document.assert_called_once_with(
            "telegram-token",
            "123",
            output,
            f"response-{job.pk}.md",
            caption="LLM response is attached as a text file.",
            reply_to_message_id=456,
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.sent_at)
        self.assertIsNone(job.error)
