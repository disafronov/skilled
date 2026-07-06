"""Tests for Q2 schedule setup."""

from django.conf import settings
from django.test import TestCase
from django_q.models import Schedule

from engine.common.schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
)
from engine.telegram.apps import MANAGED_SCHEDULES

_SYNC = make_sync_handler(MANAGED_SCHEDULES)
_RESTORE = make_restore_handler(MANAGED_SCHEDULES)
_RECREATE = make_recreate_handler(MANAGED_SCHEDULES)


class TelegramQ2ScheduleTests(TestCase):
    """Test the pipeline schedule configuration."""

    def test_default_schedules_are_created_by_name(self):
        _SYNC(sender=None)

        schedules = {
            schedule.name: schedule
            for schedule in Schedule.objects.filter(
                name__in=[
                    "telegram_ingest",
                    "telegram_deliver",
                    "telegram_intake_flush",
                    "processing",
                ]
            )
        }

        self.assertEqual(
            schedules["telegram_ingest"].func, "engine.telegram.tasks.telegram_ingest"
        )
        self.assertEqual(schedules["telegram_ingest"].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules["telegram_ingest"].minutes, 1)
        self.assertIsNone(schedules["telegram_ingest"].cron)
        self.assertEqual(schedules["telegram_ingest"].repeats, -1)

        self.assertEqual(
            schedules["telegram_deliver"].func, "engine.telegram.tasks.telegram_deliver"
        )
        self.assertEqual(schedules["telegram_deliver"].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules["telegram_deliver"].minutes, 1)
        self.assertIsNone(schedules["telegram_deliver"].cron)
        self.assertEqual(schedules["telegram_deliver"].repeats, -1)

        self.assertEqual(
            schedules["telegram_intake_flush"].func,
            "engine.telegram.tasks.telegram_flush_intake_buffers",
        )
        self.assertEqual(
            schedules["telegram_intake_flush"].schedule_type, Schedule.MINUTES
        )
        self.assertEqual(schedules["telegram_intake_flush"].minutes, 1)
        self.assertIsNone(schedules["telegram_intake_flush"].cron)
        self.assertEqual(schedules["telegram_intake_flush"].repeats, -1)

        self.assertEqual(schedules["processing"].func, settings.Q2_PROCESSING_FUNC)
        self.assertEqual(schedules["processing"].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules["processing"].minutes, 1)
        self.assertIsNone(schedules["processing"].cron)
        self.assertEqual(schedules["processing"].repeats, -1)

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        _SYNC(sender=None)
        schedule = Schedule.objects.get(name="telegram_ingest")

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

    def test_managed_schedule_uses_settings_minutes(self):
        with self.settings(Q2_TELEGRAM_INGEST_MINUTES=5):
            _SYNC(sender=None)

            schedule = Schedule.objects.get(name="telegram_ingest")
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
        schedule = Schedule.objects.get(name="telegram_ingest")
        schedule.delete()
        _RECREATE(Schedule, Schedule(name="telegram_ingest"))

        self.assertTrue(Schedule.objects.filter(name="telegram_ingest").exists())

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
        _RECREATE(Schedule, Schedule(name="custom"))

        self.assertFalse(Schedule.objects.filter(id=99).exists())


class ProcessingQ2ScheduleTests(TestCase):
    """Test the processing schedule configuration."""

    def test_processing_edits_are_overwritten_on_save(self):
        _SYNC(sender=None)

        schedule = Schedule.objects.get(name="processing")
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

    def test_processing_uses_settings_minutes(self):
        with self.settings(Q2_PROCESSING_MINUTES=5):
            _SYNC(sender=None)

            schedule = Schedule.objects.get(name="processing")
            self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
            self.assertEqual(schedule.minutes, 5)
            self.assertIsNone(schedule.cron)

            schedule.minutes = 1
            schedule.save()
            schedule.refresh_from_db()
            self.assertEqual(schedule.minutes, 5)

    def test_duplicate_processing_schedule_is_removed(self):
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

    def test_processing_recreated_on_delete(self):
        _SYNC(sender=None)
        schedule = Schedule.objects.get(name="processing")
        schedule.delete()
        _RECREATE(Schedule, Schedule(name="processing"))

        self.assertTrue(Schedule.objects.filter(name="processing").exists())
