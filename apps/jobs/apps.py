import os

from django.apps import AppConfig
from django.core.management.color import no_style
from django.db import connection
from django.db.models.signals import post_migrate, pre_save

MANAGED_SCHEDULES = (
    {
        "id": 1,
        "name": "telegram_ingest",
        "func": "apps.jobs.tasks.telegram_ingest",
        "cron_env": "Q2_TELEGRAM_INGEST_CRON",
    },
    {
        "id": 2,
        "name": "llm_worker",
        "func": "apps.jobs.tasks.llm_worker",
        "cron_env": "Q2_LLM_WORKER_CRON",
    },
    {
        "id": 3,
        "name": "telegram_deliver",
        "func": "apps.jobs.tasks.telegram_deliver",
        "cron_env": "Q2_TELEGRAM_DELIVER_CRON",
    },
)


def _managed_schedule_defaults(schedule, schedule_model):
    return {
        "name": schedule["name"],
        "func": schedule["func"],
        "hook": None,
        "args": None,
        "kwargs": None,
        "schedule_type": schedule_model.CRON,
        "minutes": None,
        "repeats": -1,
        "cron": os.environ.get(schedule["cron_env"], "* * * * *"),
        "cluster": None,
        "intended_date_kwarg": None,
    }


def protect_managed_schedule(sender, instance, **kwargs):
    """Force managed django-q schedules back to their code-defined values."""
    schedules_by_id = {schedule["id"]: schedule for schedule in MANAGED_SCHEDULES}
    schedule = schedules_by_id.get(instance.pk)
    if not schedule:
        return

    for field, value in _managed_schedule_defaults(schedule, sender).items():
        setattr(instance, field, value)


def create_schedules(sender, **kwargs):
    """Ensure core pipeline schedules exist in django-q2."""
    from django_q.models import Schedule

    schedule_ids = [schedule["id"] for schedule in MANAGED_SCHEDULES]
    schedule_names = [schedule["name"] for schedule in MANAGED_SCHEDULES]
    Schedule.objects.filter(name__in=schedule_names).exclude(
        id__in=schedule_ids
    ).delete()

    for schedule in MANAGED_SCHEDULES:
        Schedule.objects.update_or_create(
            id=schedule["id"],
            defaults=_managed_schedule_defaults(schedule, Schedule),
        )

    with connection.cursor() as cursor:
        for sql in connection.ops.sequence_reset_sql(no_style(), [Schedule]):
            cursor.execute(sql)


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.jobs"

    def ready(self) -> None:
        post_migrate.connect(create_schedules, sender=self)
        from django_q.models import Schedule

        pre_save.connect(
            protect_managed_schedule,
            sender=Schedule,
            dispatch_uid="jobs.protect_managed_q2_schedules",
        )
