"""AppConfig for engine.processing — pipeline schedule (ID 4)."""

from django.apps import AppConfig
from django.db.models.signals import post_migrate, pre_delete, pre_save

from engine.common.schedules import (
    make_deny_delete_handler,
    make_restore_handler,
    make_sync_handler,
)

MANAGED_SCHEDULES = (
    {
        "id": 4,
        "name": "processing",
        "func": "engine.processing.proxy.worker",
        "minutes_env": "Q2_PROCESSING_MINUTES",
        "default_minutes": 1,
    },
)


class ProcessingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine.processing"
    label = "processing"

    def ready(self) -> None:
        # post_migrate (not ready()) avoids DB queries on every manage.py command
        post_migrate.connect(make_sync_handler(MANAGED_SCHEDULES), sender=self)

        from django_q.models import Schedule

        pre_save.connect(
            make_restore_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="processing.protect_managed_q2_schedules",
        )
        pre_delete.connect(
            make_deny_delete_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="processing.protect_managed_q2_schedule_delete",
        )
