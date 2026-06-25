import os

from django.apps import AppConfig
from django.db.models.signals import post_migrate


def create_schedules(sender, **kwargs):
    """Ensure core pipeline schedules exist in django-q2."""
    from django_q.models import Schedule

    tasks = [
        {
            "name": "telegram_ingest",
            "func": "apps.jobs.tasks.telegram_ingest",
            "schedule_type": Schedule.CRON,
            "cron": os.environ.get("Q2_TELEGRAM_INGEST_CRON", "* * * * *"),
            "repeats": -1,
        },
        {
            "name": "llm_worker",
            "func": "apps.jobs.tasks.llm_worker",
            "schedule_type": Schedule.CRON,
            "cron": os.environ.get("Q2_LLM_WORKER_CRON", "* * * * *"),
            "repeats": -1,
        },
        {
            "name": "telegram_deliver",
            "func": "apps.jobs.tasks.telegram_deliver",
            "schedule_type": Schedule.CRON,
            "cron": os.environ.get("Q2_TELEGRAM_DELIVER_CRON", "* * * * *"),
            "repeats": -1,
        },
    ]

    for task in tasks:
        Schedule.objects.update_or_create(
            name=task["name"],
            defaults={
                "func": task["func"],
                "schedule_type": task["schedule_type"],
                "cron": task["cron"],
                "repeats": task["repeats"],
            },
        )


class JobsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.jobs"

    def ready(self) -> None:
        post_migrate.connect(create_schedules, sender=self)
