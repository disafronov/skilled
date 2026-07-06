"""Namespace engine-managed Q2 schedule names."""

from django.db import migrations

SCHEDULE_NAME_RENAMES = {
    "telegram_ingest": "engine.telegram.ingest",
    "telegram_deliver": "engine.telegram.deliver",
    "telegram_intake_flush": "engine.telegram.intake_flush",
    "processing": "engine.processing",
}


def namespace_schedule_names(apps, schema_editor):
    """Rename existing engine-managed schedule rows to stable namespaced names."""
    Schedule = apps.get_model("django_q", "Schedule")
    for old_name, new_name in SCHEDULE_NAME_RENAMES.items():
        Schedule.objects.filter(name=old_name).update(name=new_name)


def unnamespace_schedule_names(apps, schema_editor):
    """Restore previous un-namespaced schedule names."""
    Schedule = apps.get_model("django_q", "Schedule")
    for old_name, new_name in SCHEDULE_NAME_RENAMES.items():
        Schedule.objects.filter(name=new_name).update(name=old_name)


class Migration(migrations.Migration):
    dependencies = [
        ("django_q", "0019_alter_task_options_alter_ormq_key_alter_ormq_lock_and_more"),
        ("telegram", "0007_refresh_job_error_constraints"),
    ]

    operations = [
        migrations.RunPython(namespace_schedule_names, unnamespace_schedule_names),
    ]
