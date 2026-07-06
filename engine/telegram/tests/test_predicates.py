from datetime import datetime
from datetime import timezone as dt_timezone

from django.test import TestCase

from engine.telegram.models import Bot, Job


class JobSelectionPredicatesTests(TestCase):
    """Test that job selection queries correctly identify pending jobs."""

    @classmethod
    def setUpTestData(cls):
        now = datetime.now(dt_timezone.utc)
        bot = Bot.objects.create(
            name="b",
            telegram_api_token="tok",
        )

        cls.pending = Job.objects.create(
            bot=bot,
            reply_target="1",
            raw_input="hi",
        )

        cls.in_progress = Job.objects.create(
            bot=bot,
            reply_target="2",
            raw_input="hi2",
            processing_started_at=now,
        )

        cls.completed = Job.objects.create(
            bot=bot,
            reply_target="3",
            raw_input="hi3",
            raw_output="some response",
            processing_started_at=now,
            processing_finished_at=now,
        )

        cls.failed = Job.objects.create(
            bot=bot,
            reply_target="4",
            raw_input="hi4",
            processing_started_at=now,
            processing_finished_at=now,
            error="something went wrong",
        )

    def test_pending_job_selected(self):
        qs = Job.objects.ready_for_processing()
        self.assertIn(self.pending, qs)
        self.assertNotIn(self.in_progress, qs)
        self.assertNotIn(self.completed, qs)
        self.assertNotIn(self.failed, qs)

    def test_deliverable_job_selected(self):
        qs = Job.objects.ready_for_delivery()
        self.assertIn(self.completed, qs)
        self.assertIn(self.failed, qs)
        self.assertNotIn(self.pending, qs)
        self.assertNotIn(self.in_progress, qs)


class DerivedJobStatesTests(TestCase):
    """Test that job state is correctly derived from timestamps and error."""

    @classmethod
    def setUpTestData(cls):
        now = datetime.now(dt_timezone.utc)
        bot = Bot.objects.create(
            name="b",
            telegram_api_token="tok",
        )

        cls.pending = Job.objects.create(
            bot=bot,
            reply_target="1",
            raw_input="hi",
        )
        cls.processing = Job.objects.create(
            bot=bot,
            reply_target="2",
            raw_input="hi2",
            processing_started_at=now,
        )
        cls.done = Job.objects.create(
            bot=bot,
            reply_target="3",
            raw_input="hi3",
            processing_started_at=now,
            processing_finished_at=now,
            raw_output="resp",
        )
        cls.failed = Job.objects.create(
            bot=bot,
            reply_target="4",
            raw_input="hi4",
            processing_started_at=now,
            processing_finished_at=now,
            error="fail",
        )

    def assert_state(self, job, pending, processing, completed, failed):
        self.assertEqual(
            job.processing_started_at is None
            and job.processing_finished_at is None
            and job.error is None,
            pending,
        )
        self.assertEqual(
            job.processing_started_at is not None
            and job.processing_finished_at is None
            and job.error is None,
            processing,
        )
        self.assertEqual(
            job.processing_finished_at is not None
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
