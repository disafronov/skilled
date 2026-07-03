"""Update django-q2 schedule function paths after apps.jobs → engine.telegram refactor."""

from django.db import migrations

OLD_TO_NEW = {
    "apps.jobs.tasks.telegram_ingest": "engine.telegram.tasks.telegram_ingest",
    "apps.jobs.tasks.telegram_deliver": "engine.telegram.tasks.telegram_deliver",
    "apps.jobs.tasks.llm_worker": "engine.workers.proxy.worker",
}


def update_schedule_func(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    for old, new in OLD_TO_NEW.items():
        Schedule.objects.filter(func=old).update(func=new)


def reverse_schedule_func(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    for old, new in OLD_TO_NEW.items():
        Schedule.objects.filter(func=new).update(func=old)


class Migration(migrations.Migration):

    dependencies = [
        (
            "telegram",
            "0003_remove_job_tg_job_raw_output_requires_llm_finished_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            update_schedule_func,
            reverse_schedule_func,
            elidable=True,
        ),
    ]
