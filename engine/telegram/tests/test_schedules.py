"""Tests for telegram pipeline Q2 schedule setup (IDs 1–4)."""

import os
from unittest.mock import patch

from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django_q.models import Schedule

from engine.common.schedules import (
    make_deny_delete_handler,
    make_restore_handler,
    make_sync_handler,
)
from engine.telegram.apps import MANAGED_SCHEDULES

_SYNC = make_sync_handler(MANAGED_SCHEDULES)
_RESTORE = make_restore_handler(MANAGED_SCHEDULES)
_DENY_DELETE = make_deny_delete_handler(MANAGED_SCHEDULES)


class TelegramQ2ScheduleTests(TestCase):
    """Test the pipeline schedule configuration."""

    def test_default_schedules_are_hardcoded_with_fixed_ids(self):
        _SYNC(sender=None)

        schedules = {
            schedule.id: schedule
            for schedule in Schedule.objects.filter(id__in=[1, 2, 3])
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

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        _SYNC(sender=None)
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
            {"Q2_TELEGRAM_INGEST_MINUTES": "5"},
        ):
            _SYNC(sender=None)

            schedule = Schedule.objects.get(id=1)
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
                    name="telegram_ingest",
                    func="wrong.func",
                    schedule_type=Schedule.MINUTES,
                    minutes=1,
                    repeats=-1,
                )
            ]
        )

        _SYNC(sender=None)

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

        _RESTORE(Schedule, schedule)

        self.assertEqual(schedule.name, "custom")
        self.assertEqual(schedule.minutes, 10)

    def test_managed_schedule_delete_is_blocked(self):
        _SYNC(sender=None)
        schedule = Schedule.objects.get(id=1)

        with self.assertRaises(ProtectedError):
            schedule.delete()

    def test_unmanaged_schedule_delete_allowed(self):
        schedule = Schedule.objects.create(
            id=99,
            name="custom",
            func="custom.func",
            schedule_type=Schedule.MINUTES,
            minutes=10,
            repeats=-1,
        )

        _DENY_DELETE(Schedule, schedule)
        schedule.delete()

        self.assertFalse(Schedule.objects.filter(id=99).exists())
