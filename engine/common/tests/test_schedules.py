"""Tests for shared django-q2 schedule lifecycle utilities."""

from django.test import TestCase, override_settings
from django_q.models import Schedule

from ..schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
    schedule_defaults,
)

_SAMPLE_SCHEDULES = (
    {
        "name": "test_job",
        "func": "test.module.func",
        "minutes": "TEST_JOB_MINUTES",
    },
)


class ScheduleDefaultsTests(TestCase):
    @override_settings(TEST_JOB_MINUTES=10)
    def test_returns_expected_defaults(self):
        entry = _SAMPLE_SCHEDULES[0]
        defaults = schedule_defaults(entry, Schedule)

        self.assertEqual(defaults["name"], "test_job")
        self.assertEqual(defaults["func"], "test.module.func")
        self.assertIsNone(defaults["hook"])
        self.assertIsNone(defaults["args"])
        self.assertIsNone(defaults["kwargs"])
        self.assertEqual(defaults["schedule_type"], Schedule.MINUTES)
        self.assertEqual(defaults["minutes"], 10)
        self.assertIsNone(defaults["cron"])
        self.assertIsNone(defaults["cluster"])
        self.assertEqual(defaults["repeats"], -1)

    @override_settings(TEST_JOB_MINUTES=7)
    def test_reads_minutes_from_settings(self):
        defaults = schedule_defaults(_SAMPLE_SCHEDULES[0], Schedule)
        self.assertEqual(defaults["minutes"], 7)

    @override_settings(TEST_JOB_MINUTES=10)
    def test_uses_default_minutes_from_settings(self):
        entry = _SAMPLE_SCHEDULES[0]
        defaults = schedule_defaults(entry, Schedule)
        self.assertEqual(defaults["minutes"], 10)


class RestoreHandlerTests(TestCase):
    @override_settings(TEST_JOB_MINUTES=10)
    def test_restores_managed_schedule_on_pre_save(self):
        handler = make_restore_handler(_SAMPLE_SCHEDULES)
        schedule = Schedule.objects.create(
            name="test_job",
            func="test.module.func",
            schedule_type=Schedule.MINUTES,
            minutes=10,
            repeats=-1,
        )

        schedule.name = "changed"
        schedule.func = "changed.func"
        schedule.schedule_type = Schedule.HOURLY
        schedule.minutes = 99
        schedule.repeats = 10

        handler(sender=Schedule, instance=schedule)

        self.assertEqual(schedule.name, "test_job")
        self.assertEqual(schedule.func, "test.module.func")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 10)
        self.assertEqual(schedule.repeats, -1)

    @override_settings(TEST_JOB_MINUTES=10)
    def test_restores_new_duplicate_by_managed_name(self):
        handler = make_restore_handler(_SAMPLE_SCHEDULES)
        schedule = Schedule(
            name="test_job",
            func="changed.func",
            schedule_type=Schedule.HOURLY,
            minutes=99,
            repeats=10,
        )

        handler(sender=Schedule, instance=schedule)

        self.assertEqual(schedule.name, "test_job")
        self.assertEqual(schedule.func, "test.module.func")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 10)
        self.assertEqual(schedule.repeats, -1)

    def test_ignores_unmanaged_schedule(self):
        handler = make_restore_handler(_SAMPLE_SCHEDULES)
        schedule = Schedule(
            id=999,
            name="custom",
            func="custom.func",
            schedule_type=Schedule.MINUTES,
            minutes=5,
            repeats=-1,
        )

        handler(sender=Schedule, instance=schedule)

        self.assertEqual(schedule.name, "custom")
        self.assertEqual(schedule.minutes, 5)


class RecreateHandlerTests(TestCase):
    @override_settings(TEST_JOB_MINUTES=10)
    def test_recreates_managed_schedule(self):
        handler = make_recreate_handler(_SAMPLE_SCHEDULES)
        schedule = Schedule.objects.create(
            name="test_job",
            func="test.module.func",
            schedule_type=Schedule.MINUTES,
            minutes=10,
            repeats=-1,
        )
        schedule.delete()

        handler(sender=Schedule, instance=Schedule(name="test_job"))

        self.assertTrue(Schedule.objects.filter(name="test_job").exists())

    def test_ignores_unmanaged_schedule(self):
        handler = make_recreate_handler(_SAMPLE_SCHEDULES)
        schedule = Schedule.objects.create(
            id=999,
            name="unmanaged",
            func="unmanaged.func",
            schedule_type=Schedule.MINUTES,
            minutes=10,
            repeats=-1,
        )
        schedule.delete()

        handler(sender=Schedule, instance=Schedule(name="unmanaged"))

        self.assertFalse(Schedule.objects.filter(id=999).exists())


class SyncHandlerTests(TestCase):
    @override_settings(TEST_JOB_MINUTES=10)
    def test_creates_managed_schedules(self):
        handler = make_sync_handler(_SAMPLE_SCHEDULES)
        handler(sender=None)

        schedule = Schedule.objects.get(name="test_job")
        self.assertEqual(schedule.name, "test_job")
        self.assertEqual(schedule.func, "test.module.func")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 10)
        self.assertEqual(schedule.repeats, -1)

    @override_settings(TEST_JOB_MINUTES=10)
    def test_removes_duplicate_names(self):
        Schedule.objects.create(
            name="test_job",
            func="wrong.func",
            schedule_type=Schedule.MINUTES,
            minutes=1,
            repeats=-1,
        )

        handler = make_sync_handler(_SAMPLE_SCHEDULES)
        handler(sender=None)

        self.assertEqual(Schedule.objects.filter(name="test_job").count(), 1)

    @override_settings(TEST_JOB_MINUTES=10)
    def test_updates_existing_schedule(self):
        Schedule.objects.create(
            name="test_job",
            func="old.func",
            schedule_type=Schedule.HOURLY,
            minutes=5,
            repeats=3,
        )

        handler = make_sync_handler(_SAMPLE_SCHEDULES)
        handler(sender=None)

        schedule = Schedule.objects.get(name="test_job")
        self.assertEqual(schedule.name, "test_job")
        self.assertEqual(schedule.func, "test.module.func")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)

    @override_settings(TEST_JOB_MINUTES=10)
    def test_does_not_claim_unmanaged_fixed_id(self):
        custom = Schedule.objects.create(
            id=99,
            name="custom",
            func="custom.func",
            schedule_type=Schedule.MINUTES,
            minutes=5,
            repeats=-1,
        )

        handler = make_sync_handler(_SAMPLE_SCHEDULES)
        handler(sender=None)

        custom.refresh_from_db()
        self.assertEqual(custom.name, "custom")
        self.assertTrue(Schedule.objects.filter(name="test_job").exists())
