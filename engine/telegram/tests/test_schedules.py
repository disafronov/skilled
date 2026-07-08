"""Tests for Q2 schedule setup."""

from django.conf import settings
from django.test import TestCase
from django_q.models import Schedule

from ...common.schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
)
from ..apps import MANAGED_SCHEDULES

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
                    "engine.telegram.setup",
                    "engine.telegram.ingest",
                    "engine.telegram.deliver",
                    "engine.telegram.intake_flush",
                    "engine.processing",
                ]
            )
        }

        self.assertEqual(
            schedules["engine.telegram.setup"].func,
            "engine.telegram.tasks.telegram_setup",
        )
        self.assertEqual(
            schedules["engine.telegram.setup"].schedule_type, Schedule.MINUTES
        )
        self.assertEqual(schedules["engine.telegram.setup"].minutes, 1)
        self.assertIsNone(schedules["engine.telegram.setup"].cron)
        self.assertEqual(schedules["engine.telegram.setup"].repeats, -1)

        self.assertEqual(
            schedules["engine.telegram.ingest"].func,
            "engine.telegram.tasks.telegram_ingest",
        )
        self.assertEqual(
            schedules["engine.telegram.ingest"].schedule_type, Schedule.MINUTES
        )
        self.assertEqual(schedules["engine.telegram.ingest"].minutes, 1)
        self.assertIsNone(schedules["engine.telegram.ingest"].cron)
        self.assertEqual(schedules["engine.telegram.ingest"].repeats, -1)

        self.assertEqual(
            schedules["engine.telegram.deliver"].func,
            "engine.telegram.tasks.telegram_deliver",
        )
        self.assertEqual(
            schedules["engine.telegram.deliver"].schedule_type, Schedule.MINUTES
        )
        self.assertEqual(schedules["engine.telegram.deliver"].minutes, 1)
        self.assertIsNone(schedules["engine.telegram.deliver"].cron)
        self.assertEqual(schedules["engine.telegram.deliver"].repeats, -1)

        self.assertEqual(
            schedules["engine.telegram.intake_flush"].func,
            "engine.telegram.tasks.telegram_flush_intake_buffers",
        )
        self.assertEqual(
            schedules["engine.telegram.intake_flush"].schedule_type, Schedule.MINUTES
        )
        self.assertEqual(schedules["engine.telegram.intake_flush"].minutes, 1)
        self.assertIsNone(schedules["engine.telegram.intake_flush"].cron)
        self.assertEqual(schedules["engine.telegram.intake_flush"].repeats, -1)

        self.assertEqual(
            schedules["engine.processing"].func, settings.Q2_PROCESSING_FUNC
        )
        self.assertEqual(schedules["engine.processing"].schedule_type, Schedule.MINUTES)
        self.assertEqual(schedules["engine.processing"].minutes, 1)
        self.assertIsNone(schedules["engine.processing"].cron)
        self.assertEqual(schedules["engine.processing"].repeats, -1)

    def test_managed_schedule_edits_are_overwritten_on_save(self):
        _SYNC(sender=None)
        schedule = Schedule.objects.get(name="engine.telegram.ingest")

        schedule.name = "changed"
        schedule.func = "changed.func"
        schedule.schedule_type = Schedule.HOURLY
        schedule.minutes = 15
        schedule.repeats = 10
        schedule.save()

        schedule.refresh_from_db()
        self.assertEqual(schedule.name, "engine.telegram.ingest")
        self.assertEqual(schedule.func, "engine.telegram.tasks.telegram_ingest")
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 1)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_setup_schedule_uses_settings_minutes(self):
        with self.settings(Q2_TELEGRAM_SETUP_MINUTES=5):
            _SYNC(sender=None)

            schedule = Schedule.objects.get(name="engine.telegram.setup")
            self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
            self.assertEqual(schedule.minutes, 5)
            self.assertIsNone(schedule.cron)

            schedule.minutes = 1
            schedule.save()
            schedule.refresh_from_db()
            self.assertEqual(schedule.minutes, 5)

    def test_managed_schedule_uses_settings_minutes(self):
        with self.settings(Q2_TELEGRAM_INGEST_MINUTES=5):
            _SYNC(sender=None)

            schedule = Schedule.objects.get(name="engine.telegram.ingest")
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
                    name="engine.telegram.ingest",
                    func="wrong.func",
                    schedule_type=Schedule.MINUTES,
                    minutes=1,
                    repeats=-1,
                )
            ]
        )

        _SYNC(sender=None)

        self.assertEqual(
            Schedule.objects.filter(name="engine.telegram.ingest").count(), 1
        )

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
        schedule = Schedule.objects.get(name="engine.telegram.ingest")
        schedule.delete()
        _RECREATE(Schedule, Schedule(name="engine.telegram.ingest"))

        self.assertTrue(Schedule.objects.filter(name="engine.telegram.ingest").exists())

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

        schedule = Schedule.objects.get(name="engine.processing")
        schedule.name = "changed"
        schedule.func = "changed.func"
        schedule.schedule_type = Schedule.HOURLY
        schedule.minutes = 15
        schedule.repeats = 10
        schedule.save()

        schedule.refresh_from_db()
        self.assertEqual(schedule.name, "engine.processing")
        self.assertEqual(schedule.func, settings.Q2_PROCESSING_FUNC)
        self.assertEqual(schedule.schedule_type, Schedule.MINUTES)
        self.assertEqual(schedule.minutes, 1)
        self.assertIsNone(schedule.cron)
        self.assertEqual(schedule.repeats, -1)

    def test_processing_uses_settings_minutes(self):
        with self.settings(Q2_PROCESSING_MINUTES=5):
            _SYNC(sender=None)

            schedule = Schedule.objects.get(name="engine.processing")
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
                    name="engine.processing",
                    func="wrong.func",
                    schedule_type=Schedule.MINUTES,
                    minutes=1,
                    repeats=-1,
                )
            ]
        )

        _SYNC(sender=None)

        self.assertEqual(Schedule.objects.filter(name="engine.processing").count(), 1)

    def test_processing_recreated_on_delete(self):
        _SYNC(sender=None)
        schedule = Schedule.objects.get(name="engine.processing")
        schedule.delete()
        _RECREATE(Schedule, Schedule(name="engine.processing"))

        self.assertTrue(Schedule.objects.filter(name="engine.processing").exists())
