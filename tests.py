import os
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from django.test import TestCase
from django.utils import timezone
from django_q.models import Schedule, Task

from apps.bots.models import Bot
from apps.inference.models import Profile, Provider
from apps.jobs.apps import create_schedules
from apps.jobs.models import Job
from apps.jobs.tasks import (
    QUEUE_ACK_TEXT,
    cleanup_q2_successes,
    telegram_deliver,
    telegram_ingest,
)
from apps.library.models import Skill, Wrapper
from workers.llm import build_request_body, get_global_system_prompt
from workers.telegram import (
    TELEGRAM_DOCUMENT_FORMAT_HTML,
    TELEGRAM_DOCUMENT_FORMAT_MARKDOWN,
    TELEGRAM_DOCUMENT_FORMAT_TEXT,
    TELEGRAM_MESSAGE_CHAR_LIMIT,
    TELEGRAM_PARSE_MODE_HTML,
    TELEGRAM_PARSE_MODE_MARKDOWN_V2,
    _raise_for_status,
    detect_document_format,
    detect_parse_mode,
    document_format_content_type,
    document_format_filename,
    prepare_message_text,
)


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

    def test_global_system_prompt_loaded_from_file(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "policy.md"
            path.write_text("Always be concise.\n", encoding="utf-8")

            with patch.dict(os.environ, {"POLICY_FILE": str(path)}):
                self.assertEqual(get_global_system_prompt(), "Always be concise.")

    def test_empty_global_system_prompt_file_returns_empty_string(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "policy.md"
            path.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"POLICY_FILE": str(path)}):
                self.assertEqual(get_global_system_prompt(), "")

    def test_missing_global_system_prompt_file_returns_empty_string(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.md"

            with patch.dict(os.environ, {"POLICY_FILE": str(path)}):
                self.assertEqual(get_global_system_prompt(), "")


class TelegramClientTests(TestCase):
    """Test Telegram API error handling."""

    def test_detects_html_parse_mode(self):
        self.assertEqual(
            detect_parse_mode("<b>Hello</b>"),
            TELEGRAM_PARSE_MODE_HTML,
        )

    def test_standard_html_has_no_telegram_parse_mode(self):
        self.assertIsNone(detect_parse_mode("<div>Hello</div>"))

    def test_detects_markdown_parse_mode(self):
        self.assertEqual(
            detect_parse_mode("*Hello*"),
            TELEGRAM_PARSE_MODE_MARKDOWN_V2,
        )

    def test_standard_markdown_has_no_telegram_parse_mode(self):
        self.assertIsNone(detect_parse_mode("**Hello**"))

    def test_plain_text_has_no_parse_mode(self):
        self.assertIsNone(detect_parse_mode("short response"))

    def test_detects_document_formats(self):
        self.assertEqual(
            detect_document_format("<b>Hello</b>"),
            TELEGRAM_DOCUMENT_FORMAT_HTML,
        )
        self.assertEqual(
            detect_document_format("<div>Hello</div>"),
            TELEGRAM_DOCUMENT_FORMAT_HTML,
        )
        self.assertEqual(
            detect_document_format("**Hello**"),
            TELEGRAM_DOCUMENT_FORMAT_MARKDOWN,
        )
        self.assertEqual(
            detect_document_format("Hello"),
            TELEGRAM_DOCUMENT_FORMAT_TEXT,
        )

    def test_document_format_metadata(self):
        self.assertEqual(
            document_format_filename(123, TELEGRAM_DOCUMENT_FORMAT_HTML),
            "response-123.html",
        )
        self.assertEqual(
            document_format_filename(123, TELEGRAM_DOCUMENT_FORMAT_MARKDOWN),
            "response-123.md",
        )
        self.assertEqual(
            document_format_filename(123, TELEGRAM_DOCUMENT_FORMAT_TEXT),
            "response-123.txt",
        )
        self.assertEqual(
            document_format_content_type(TELEGRAM_DOCUMENT_FORMAT_HTML),
            "text/html",
        )
        self.assertEqual(
            document_format_content_type(TELEGRAM_DOCUMENT_FORMAT_MARKDOWN),
            "text/markdown",
        )
        self.assertEqual(
            document_format_content_type(TELEGRAM_DOCUMENT_FORMAT_TEXT),
            "text/plain",
        )

    def test_markdown_text_is_escaped_for_markdown_v2(self):
        self.assertEqual(
            prepare_message_text("*Hello_world*", TELEGRAM_PARSE_MODE_MARKDOWN_V2),
            r"*Hello\_world*",
        )

    def test_plain_message_text_removes_control_chars(self):
        self.assertEqual(
            prepare_message_text("hello\x00\x08\nworld", None),
            "hello\nworld",
        )

    def test_html_message_text_is_sanitized(self):
        self.assertEqual(
            prepare_message_text(
                '<b onclick="x">hello</b><script>alert(1)</script>',
                TELEGRAM_PARSE_MODE_HTML,
            ),
            "<b>hello</b>alert(1)",
        )

    def test_html_message_text_allows_safe_links(self):
        self.assertEqual(
            prepare_message_text(
                '<a href="https://example.com" onclick="x">site</a>',
                TELEGRAM_PARSE_MODE_HTML,
            ),
            '<a href="https://example.com">site</a>',
        )

    def test_html_message_text_drops_unsafe_links(self):
        self.assertEqual(
            prepare_message_text(
                '<a href="javascript:alert(1)">site</a>',
                TELEGRAM_PARSE_MODE_HTML,
            ),
            "<a>site</a>",
        )

    def test_http_error_includes_response_body(self):
        request = httpx.Request("POST", "https://api.telegram.org/botx/sendMessage")
        response = httpx.Response(
            400,
            request=request,
            text='{"ok":false,"description":"Bad Request: message is too long"}',
        )

        with self.assertRaisesRegex(RuntimeError, "message is too long"):
            _raise_for_status(response)


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

    def test_default_schedules_are_hardcoded_with_fixed_ids(self):
        create_schedules(sender=None)

        schedules = {
            schedule.id: schedule
            for schedule in Schedule.objects.filter(id__in=[1, 2, 3, 4])
        }

        self.assertEqual(schedules[1].name, "telegram_ingest")
        self.assertEqual(schedules[1].func, "apps.jobs.tasks.telegram_ingest")
        self.assertEqual(schedules[1].schedule_type, Schedule.CRON)
        self.assertEqual(schedules[1].cron, "* * * * *")
        self.assertEqual(schedules[1].repeats, -1)

        self.assertEqual(schedules[2].name, "llm_worker")
        self.assertEqual(schedules[2].func, "apps.jobs.tasks.llm_worker")
        self.assertEqual(schedules[2].schedule_type, Schedule.CRON)
        self.assertEqual(schedules[2].cron, "* * * * *")
        self.assertEqual(schedules[2].repeats, -1)

        self.assertEqual(schedules[3].name, "telegram_deliver")
        self.assertEqual(schedules[3].func, "apps.jobs.tasks.telegram_deliver")
        self.assertEqual(schedules[3].schedule_type, Schedule.CRON)
        self.assertEqual(schedules[3].cron, "* * * * *")
        self.assertEqual(schedules[3].repeats, -1)

        self.assertEqual(schedules[4].name, "q2_success_cleanup")
        self.assertEqual(schedules[4].func, "apps.jobs.tasks.cleanup_q2_successes")
        self.assertEqual(schedules[4].schedule_type, Schedule.CRON)
        self.assertEqual(schedules[4].cron, "0 * * * *")
        self.assertEqual(schedules[4].repeats, -1)

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        create_schedules(sender=None)
        schedule = Schedule.objects.get(id=1)

        schedule.name = "changed"
        schedule.func = "changed.func"
        schedule.schedule_type = Schedule.HOURLY
        schedule.cron = "0 0 * * *"
        schedule.repeats = 10
        schedule.save()

        schedule.refresh_from_db()
        self.assertEqual(schedule.name, "telegram_ingest")
        self.assertEqual(schedule.func, "apps.jobs.tasks.telegram_ingest")
        self.assertEqual(schedule.schedule_type, Schedule.CRON)
        self.assertEqual(schedule.cron, "* * * * *")
        self.assertEqual(schedule.repeats, -1)

    def test_managed_schedule_uses_env_cron(self):
        with patch.dict(
            os.environ,
            {
                "Q2_TELEGRAM_INGEST_CRON": "*/5 * * * *",
                "Q2_SUCCESS_CLEANUP_CRON": "30 * * * *",
            },
        ):
            create_schedules(sender=None)

            schedule = Schedule.objects.get(id=1)
            self.assertEqual(schedule.cron, "*/5 * * * *")
            cleanup_schedule = Schedule.objects.get(id=4)
            self.assertEqual(cleanup_schedule.cron, "30 * * * *")

            schedule.cron = "0 0 * * *"
            schedule.save()
            schedule.refresh_from_db()
            self.assertEqual(schedule.cron, "*/5 * * * *")

    def test_duplicate_managed_schedules_are_removed(self):
        Schedule.objects.create(
            name="telegram_ingest",
            func="wrong.func",
            schedule_type=Schedule.CRON,
            cron="0 0 * * *",
            repeats=-1,
        )

        create_schedules(sender=None)

        self.assertEqual(Schedule.objects.filter(name="telegram_ingest").count(), 1)
        self.assertEqual(Schedule.objects.get(name="telegram_ingest").id, 1)


class Q2SuccessCleanupTests(TestCase):
    """Test django-q2 successful task retention cleanup."""

    def test_cleanup_deletes_only_expired_success_tasks(self):
        now = timezone.now()
        old = now - timedelta(seconds=120)
        fresh = now - timedelta(seconds=30)

        old_success = Task.objects.create(
            id="old_success",
            name="old_success",
            func="tests.task",
            started=old,
            stopped=old,
            success=True,
        )
        fresh_success = Task.objects.create(
            id="fresh_success",
            name="fresh_success",
            func="tests.task",
            started=fresh,
            stopped=fresh,
            success=True,
        )
        old_failure = Task.objects.create(
            id="old_failure",
            name="old_failure",
            func="tests.task",
            started=old,
            stopped=old,
            success=False,
        )

        with patch.dict(os.environ, {"Q2_SUCCESS_TASK_RETENTION_SECONDS": "60"}):
            cleanup_q2_successes()

        self.assertFalse(Task.objects.filter(id=old_success.id).exists())
        self.assertTrue(Task.objects.filter(id=fresh_success.id).exists())
        self.assertTrue(Task.objects.filter(id=old_failure.id).exists())


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
            parse_mode=None,
        )
        send_document.assert_not_called()
        job.refresh_from_db()
        self.assertIsNotNone(job.sent_at)
        self.assertIsNone(job.error)

    @patch("apps.jobs.tasks.send_document")
    @patch("apps.jobs.tasks.send_message")
    def test_markdown_response_sent_with_markdown_parse_mode(
        self,
        send_message,
        send_document,
    ):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output="*bold*",
            received_at=self.now,
            llm_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_called_once_with(
            "telegram-token",
            "123",
            "*bold*",
            reply_to_message_id=456,
            parse_mode=TELEGRAM_PARSE_MODE_MARKDOWN_V2,
        )
        send_document.assert_not_called()
        job.refresh_from_db()
        self.assertIsNotNone(job.sent_at)
        self.assertIsNone(job.error)

    @patch("apps.jobs.tasks.send_document")
    @patch("apps.jobs.tasks.send_message")
    def test_html_response_sent_with_html_parse_mode(self, send_message, send_document):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            reply_to_message_id=456,
            raw_input="hi",
            raw_output="<b>bold</b>",
            received_at=self.now,
            llm_finished_at=self.now,
        )

        telegram_deliver()

        send_message.assert_called_once_with(
            "telegram-token",
            "123",
            "<b>bold</b>",
            reply_to_message_id=456,
            parse_mode=TELEGRAM_PARSE_MODE_HTML,
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
        output = ("x" * (TELEGRAM_MESSAGE_CHAR_LIMIT + 1)) + "\x08"
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
            f"response-{job.pk}.txt",
            "text/plain",
            caption="LLM response is attached as a text file.",
            reply_to_message_id=456,
        )
        job.refresh_from_db()
        self.assertIsNotNone(job.sent_at)
        self.assertIsNone(job.error)

    @patch("apps.jobs.tasks.send_document")
    @patch("apps.jobs.tasks.send_message")
    def test_long_markdown_response_sent_as_markdown_document(
        self,
        send_message,
        send_document,
    ):
        output = "**bold**\n" + ("x" * TELEGRAM_MESSAGE_CHAR_LIMIT)
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
            "text/markdown",
            caption="LLM response is attached as a text file.",
            reply_to_message_id=456,
        )

    @patch("apps.jobs.tasks.send_document")
    @patch("apps.jobs.tasks.send_message")
    def test_long_html_response_sent_as_html_document(
        self,
        send_message,
        send_document,
    ):
        output = "<b>bold</b>\n" + ("x" * TELEGRAM_MESSAGE_CHAR_LIMIT)
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
            f"response-{job.pk}.html",
            "text/html",
            caption="LLM response is attached as a text file.",
            reply_to_message_id=456,
        )
