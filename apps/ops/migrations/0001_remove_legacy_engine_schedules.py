"""Remove Q2 schedules owned by the former embedded Telegram engine."""

from django.db import migrations

LEGACY_SCHEDULE_NAMES = (
    "engine.telegram.setup",
    "engine.telegram.ingest",
    "engine.telegram.deliver",
    "engine.telegram.intake_flush",
    "engine.processing",
)


def remove_legacy_engine_schedules(apps, schema_editor):
    """Delete obsolete schedules; the external app recreates its own after migrate."""
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name__in=LEGACY_SCHEDULE_NAMES).delete()


class Migration(migrations.Migration):
    """Remove schedules whose task paths refer to the deleted engine package."""

    dependencies = [
        (
            "django_q",
            "0019_alter_task_options_alter_ormq_key_alter_ormq_lock_and_more",
        ),
        ("telegram", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            remove_legacy_engine_schedules,
            migrations.RunPython.noop,
        ),
    ]
