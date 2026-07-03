"""Tests for shared django-q2 schedule lifecycle utilities."""

import os
from unittest.mock import patch

from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django_q.models import Schedule

from engine.common.schedules import (
    make_deny_delete_handler,
    make_restore_handler,
    make_sync_handler,
    schedule_defaults,
)

_SAMPLE_SCHEDULES = (
    {
        "id": 99,
        "name": "test_job",
        "func": "test.module.func",
        "minutes_env": "TEST_JOB_MINUTES",
        "default_minutes": 10,
    },
)


class ScheduleDefaultsTests(TestCase):
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

    def test_reads_minutes_from_env(self):
        with patch.dict(os.environ, {"TEST_JOB_MINUTES": "7"}):
            defaults = schedule_defaults(_SAMPLE_SCHEDULES[0], Schedule)
            self.assertEqual(defaults["minutes"], 7)

    def test_falls_back_to_default_minutes_when_env_unset(self):
        entry = _SAMPLE_SCHEDULES[0]
        defaults = schedule_defaults(entry, Schedule)
        self.assertEqual(defaults["minutes"], 10)


class RestoreHandlerTests(TestCase):
    def test_restores_managed_schedule_on_pre_save(self):
        handler = make_restore_handler(_SAMPLE_SCHEDULES)
        entry = _SAMPLE_SCHEDULES[0]

        schedule = Schedule(
            id=entry["id"],
            name="changed",
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


class DenyDeleteHandlerTests(TestCase):
    def test_blocks_managed_schedule_deletion(self):
        handler = make_deny_delete_handler(_SAMPLE_SCHEDULES)
        schedule = Schedule(id=_SAMPLE_SCHEDULES[0]["id"])

        with self.assertRaises(ProtectedError):
            handler(sender=Schedule, instance=schedule)

    def test_allows_unmanaged_schedule_deletion(self):
        handler = make_deny_delete_handler(_SAMPLE_SCHEDULES)
        schedule = Schedule(id=999)

        # Should not raise
        handler(sender=Schedule, instance=schedule)


class SyncHandlerTests(TestCase):
    def test_creates_managed_schedules(self):
        handler = make_sync_handler(_SAMPLE_SCHEDULES)
        handler(sender=None)

        schedule = Schedule.objects.get(id=_SAMPLE_SCHEDULES[0]["id"])
        self.assertEqual(schedule.name, "test_job")
        self.assertEqual(schedule.func, "test.module.func")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 10)
        self.assertEqual(schedule.repeats, -1)

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
        self.assertEqual(Schedule.objects.get(name="test_job").id, 99)

    def test_updates_existing_schedule(self):
        Schedule.objects.create(
            id=_SAMPLE_SCHEDULES[0]["id"],
            name="old_name",
            func="old.func",
            schedule_type=Schedule.HOURLY,
            minutes=5,
            repeats=3,
        )

        handler = make_sync_handler(_SAMPLE_SCHEDULES)
        handler(sender=None)

        schedule = Schedule.objects.get(id=_SAMPLE_SCHEDULES[0]["id"])
        self.assertEqual(schedule.name, "test_job")
        self.assertEqual(schedule.func, "test.module.func")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
