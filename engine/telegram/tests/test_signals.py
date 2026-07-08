from unittest.mock import patch

from django.conf import settings
from django.test import TestCase

from ..models import Bot, Job


class SignalOrchestrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bot = Bot.objects.create(
            name="sig-bot",
            telegram_api_token="telegram-token",
        )

    @patch("engine.telegram.signals.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("engine.telegram.signals.async_task")
    def test_created_schedules_worker(self, mock_async_task, mock_on_commit):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        self.assertEqual(mock_async_task.call_count, 2)
        mock_async_task.assert_any_call("engine.telegram.tasks.telegram_ack", job.pk)
        mock_async_task.assert_any_call(settings.Q2_PROCESSING_FUNC, job.pk)

    @patch("engine.telegram.signals.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("engine.telegram.signals.async_task")
    def test_processing_finished_schedules_delivery(
        self, mock_async_task, mock_on_commit
    ):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        mock_async_task.reset_mock()

        job.raw_output = "some output"
        job.processing_started_at = job.created_at
        job.processing_finished_at = job.created_at
        job.save(
            update_fields=[
                "raw_output",
                "processing_started_at",
                "processing_finished_at",
            ]
        )

        mock_async_task.assert_called_once_with(
            "engine.telegram.tasks.telegram_deliver", job.pk
        )

    @patch("engine.telegram.signals.transaction.on_commit", side_effect=lambda fn: fn())
    @patch("engine.telegram.signals.async_task")
    def test_other_update_does_not_schedule(self, mock_async_task, mock_on_commit):
        job = Job.objects.create(
            bot=self.bot,
            reply_target="123",
            raw_input="hello",
        )
        mock_async_task.reset_mock()

        job.reply_target = "456"
        job.save(update_fields=["reply_target"])

        mock_async_task.assert_not_called()
