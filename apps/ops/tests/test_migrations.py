"""Tests for ops data migrations."""

from importlib import import_module

from django.apps import apps
from django.test import TestCase
from django_q.models import Schedule

MIGRATION = import_module("apps.ops.migrations.0001_remove_legacy_engine_schedules")


class RemoveLegacyEngineSchedulesTests(TestCase):
    """Test cleanup of schedules owned by the removed embedded engine."""

    def test_removes_only_legacy_engine_schedules(self):
        schedules = [
            Schedule(
                name=name,
                func="engine.telegram.tasks.obsolete",
                schedule_type=Schedule.MINUTES,
                minutes=1,
                repeats=-1,
            )
            for name in MIGRATION.LEGACY_SCHEDULE_NAMES
        ]
        schedules.append(
            Schedule(
                name="custom",
                func="custom.task",
                schedule_type=Schedule.MINUTES,
                minutes=1,
                repeats=-1,
            )
        )
        Schedule.objects.bulk_create(schedules)

        MIGRATION.remove_legacy_engine_schedules(apps, schema_editor=None)

        self.assertFalse(
            Schedule.objects.filter(name__in=MIGRATION.LEGACY_SCHEDULE_NAMES).exists()
        )
        self.assertTrue(Schedule.objects.filter(name="custom").exists())
