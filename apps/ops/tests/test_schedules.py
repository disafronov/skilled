import os
from unittest.mock import patch

from django.test import TestCase
from django_q.models import Schedule

from apps.ops.apps import create_schedules, protect_managed_schedule


class OpsQ2ScheduleTests(TestCase):
    """Test the ops schedule configuration."""

    def test_default_cleanup_schedule_is_hardcoded_with_fixed_id(self):
        create_schedules(sender=None)

        schedule = Schedule.objects.get(id=5)

        self.assertEqual(schedule.name, "q2_success_cleanup")
        self.assertEqual(schedule.func, "apps.ops.q2.cleanup_q2_successes")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 60)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        create_schedules(sender=None)
        schedule = Schedule.objects.get(id=5)

        schedule.name = "changed"
        schedule.func = "changed.func"
        schedule.schedule_type = Schedule.HOURLY
        schedule.minutes = 15
        schedule.repeats = 10
        schedule.save()

        schedule.refresh_from_db()
        self.assertEqual(schedule.name, "q2_success_cleanup")
        self.assertEqual(schedule.func, "apps.ops.q2.cleanup_q2_successes")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 60)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_cleanup_schedule_uses_env_minutes(self):
        with patch.dict(
            os.environ,
            {"Q2_SUCCESS_CLEANUP_MINUTES": "30"},
        ):
            create_schedules(sender=None)

            schedule = Schedule.objects.get(id=5)
            self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
            self.assertEqual(schedule.minutes, 30)
            self.assertIsNone(schedule.cron)

            schedule.minutes = 1
            schedule.save()
            schedule.refresh_from_db()
            self.assertEqual(schedule.minutes, 30)

    def test_duplicate_managed_schedules_are_removed(self):
        Schedule.objects.bulk_create(
            [
                Schedule(
                    name="q2_success_cleanup",
                    func="wrong.func",
                    schedule_type=Schedule.MINUTES,
                    minutes=1,
                    repeats=-1,
                )
            ]
        )

        create_schedules(sender=None)

        self.assertEqual(Schedule.objects.filter(name="q2_success_cleanup").count(), 1)
        self.assertEqual(Schedule.objects.get(name="q2_success_cleanup").id, 5)

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
