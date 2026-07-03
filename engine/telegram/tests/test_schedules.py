import os
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from django_q.models import Schedule, Task

from engine.telegram.apps import create_schedules, protect_managed_schedule
from engine.telegram.tasks import cleanup_q2_successes


class Q2ScheduleTests(TestCase):
    """Test the pipeline schedule configuration."""

    def test_default_schedules_are_hardcoded_with_fixed_ids(self):
        create_schedules(sender=None)

        schedules = {
            schedule.id: schedule
            for schedule in Schedule.objects.filter(id__in=[1, 2, 3, 4])
        }

        self.assertEqual(schedules[1].name, "telegram_ingest")
        self.assertEqual(schedules[1].func, "engine.telegram.tasks.telegram_ingest")
        self.assertEqual(schedules[1].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules[1].minutes, 1)
        self.assertIsNone(schedules[1].cron)
        self.assertEqual(schedules[1].repeats, -1)

        self.assertEqual(schedules[2].name, "processing")
        self.assertEqual(schedules[2].func, "engine.workers.proxy.worker")
        self.assertEqual(schedules[2].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules[2].minutes, 1)
        self.assertIsNone(schedules[2].cron)
        self.assertEqual(schedules[2].repeats, -1)

        self.assertEqual(schedules[3].name, "telegram_deliver")
        self.assertEqual(schedules[3].func, "engine.telegram.tasks.telegram_deliver")
        self.assertEqual(schedules[3].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules[3].minutes, 1)
        self.assertIsNone(schedules[3].cron)
        self.assertEqual(schedules[3].repeats, -1)

        self.assertEqual(schedules[4].name, "q2_success_cleanup")
        self.assertEqual(
            schedules[4].func, "engine.telegram.tasks.cleanup_q2_successes"
        )
        self.assertEqual(schedules[4].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules[4].minutes, 60)
        self.assertIsNone(schedules[4].cron)
        self.assertEqual(schedules[4].repeats, -1)

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        create_schedules(sender=None)
        schedule = Schedule.objects.get(id=1)

        schedule.name = "changed"
        schedule.func = "changed.func"
        schedule.schedule_type = Schedule.HOURLY
        schedule.minutes = 15
        schedule.repeats = 10
        schedule.save()

        schedule.refresh_from_db()
        self.assertEqual(schedule.name, "telegram_ingest")
        self.assertEqual(schedule.func, "engine.telegram.tasks.telegram_ingest")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 1)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_managed_schedule_uses_env_minutes(self):
        with patch.dict(
            os.environ,
            {
                "Q2_TELEGRAM_INGEST_MINUTES": "5",
                "Q2_SUCCESS_CLEANUP_MINUTES": "30",
            },
        ):
            create_schedules(sender=None)

            schedule = Schedule.objects.get(id=1)
            self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
            self.assertEqual(schedule.minutes, 5)
            self.assertIsNone(schedule.cron)
            cleanup_schedule = Schedule.objects.get(id=4)
            self.assertEqual(cleanup_schedule.schedule_type, Schedule.MINUTES)
            self.assertEqual(cleanup_schedule.minutes, 30)
            self.assertIsNone(cleanup_schedule.cron)

            schedule.minutes = 1
            schedule.save()
            schedule.refresh_from_db()
            self.assertEqual(schedule.minutes, 5)

    def test_duplicate_managed_schedules_are_removed(self):
        Schedule.objects.bulk_create(
            [
                Schedule(
                    name="telegram_ingest",
                    func="wrong.func",
                    schedule_type=Schedule.MINUTES,
                    minutes=1,
                    repeats=-1,
                )
            ]
        )

        create_schedules(sender=None)

        self.assertEqual(Schedule.objects.filter(name="telegram_ingest").count(), 1)
        self.assertEqual(Schedule.objects.get(name="telegram_ingest").id, 1)

    def test_unmanaged_schedule_edits_are_ignored(self):
        schedule = Schedule(
            id=99,
            name="custom",
            func="custom.func",
            schedule_type=Schedule.MINUTES,
            minutes=10,
            repeats=-1,
        )

        protect_managed_schedule(sender=Schedule, instance=schedule)

        self.assertEqual(schedule.name, "custom")
        self.assertEqual(schedule.minutes, 10)


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
