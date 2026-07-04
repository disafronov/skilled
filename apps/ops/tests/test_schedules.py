"""Tests for ops Q2 schedule setup (ID 5)."""

from django.test import TestCase
from django_q.models import Schedule

from apps.ops.apps import MANAGED_SCHEDULES
from engine.common.schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
)

_SYNC = make_sync_handler(MANAGED_SCHEDULES)
_RESTORE = make_restore_handler(MANAGED_SCHEDULES)
_RECREATE = make_recreate_handler(MANAGED_SCHEDULES)


class OpsQ2ScheduleTests(TestCase):
    """Test the ops schedule configuration."""

    def test_default_cleanup_schedule_is_hardcoded_with_fixed_id(self):
        _SYNC(sender=None)

        schedule = Schedule.objects.get(id=5)

        self.assertEqual(schedule.name, "q2_success_cleanup")
        self.assertEqual(schedule.func, "apps.ops.q2.cleanup_q2_successes")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 60)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        _SYNC(sender=None)
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

    def test_cleanup_schedule_uses_settings_minutes(self):
        with self.settings(Q2_SUCCESS_CLEANUP_MINUTES=30):
            _SYNC(sender=None)

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

        _SYNC(sender=None)

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

        _RESTORE(Schedule, schedule)

        self.assertEqual(schedule.name, "custom")
        self.assertEqual(schedule.minutes, 10)

    def test_managed_schedule_is_recreated_on_delete(self):
        _SYNC(sender=None)
        schedule = Schedule.objects.get(id=5)
        pk = schedule.pk
        schedule.delete()
        _RECREATE(Schedule, Schedule(pk=pk))

        self.assertTrue(Schedule.objects.filter(id=pk).exists())

    def test_unmanaged_schedule_delete_is_ignored_by_recreate(self):
        schedule = Schedule.objects.create(
            id=99,
            name="custom",
            func="custom.func",
            schedule_type=Schedule.MINUTES,
            minutes=10,
            repeats=-1,
        )
        schedule.delete()
        _RECREATE(Schedule, Schedule(pk=99))

        self.assertFalse(Schedule.objects.filter(id=99).exists())
