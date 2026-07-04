"""Tests for processing Q2 schedule setup (ID 4)."""

from django.conf import settings
from django.test import TestCase
from django_q.models import Schedule

from engine.common.schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
)
from engine.proxy.apps import MANAGED_SCHEDULES

_SYNC = make_sync_handler(MANAGED_SCHEDULES)
_RESTORE = make_restore_handler(MANAGED_SCHEDULES)
_RECREATE = make_recreate_handler(MANAGED_SCHEDULES)


class ProxyQ2ScheduleTests(TestCase):
    """Test the processing schedule configuration from engine.proxy."""

    def test_default_schedule_is_hardcoded_with_fixed_id(self):
        _SYNC(sender=None)

        schedule = Schedule.objects.get(id=4)

        self.assertEqual(schedule.name, "processing")
        self.assertEqual(schedule.func, settings.Q2_PROCESSING_FUNC)
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 1)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        _SYNC(sender=None)
        schedule = Schedule.objects.get(id=4)

        schedule.name = "changed"
        schedule.func = "changed.func"
        schedule.schedule_type = Schedule.HOURLY
        schedule.minutes = 15
        schedule.repeats = 10
        schedule.save()

        schedule.refresh_from_db()
        self.assertEqual(schedule.name, "processing")
        self.assertEqual(schedule.func, settings.Q2_PROCESSING_FUNC)
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 1)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_managed_schedule_uses_settings_minutes(self):
        with self.settings(Q2_PROCESSING_MINUTES=5):
            _SYNC(sender=None)

            schedule = Schedule.objects.get(id=4)
            self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
            self.assertEqual(schedule.minutes, 5)
            self.assertIsNone(schedule.cron)

            schedule.minutes = 1
            schedule.save()
            schedule.refresh_from_db()
            self.assertEqual(schedule.minutes, 5)

    def test_duplicate_managed_schedules_are_removed(self):
        Schedule.objects.bulk_create(
            [
                Schedule(
                    name="processing",
                    func="wrong.func",
                    schedule_type=Schedule.MINUTES,
                    minutes=1,
                    repeats=-1,
                )
            ]
        )

        _SYNC(sender=None)

        self.assertEqual(Schedule.objects.filter(name="processing").count(), 1)
        self.assertEqual(Schedule.objects.get(name="processing").id, 4)

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
        schedule = Schedule.objects.get(id=4)
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
