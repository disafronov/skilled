"""Q2 schedule management for ops infrastructure tasks (ID 5)."""

from django.apps import AppConfig
from django.db.models.signals import post_delete, post_migrate, pre_save

from engine.common.schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
)

MANAGED_SCHEDULES = (
    {
        "id": 5,
        "name": "q2_success_cleanup",
        "func": "apps.ops.q2.cleanup_q2_successes",
        "minutes_env": "Q2_SUCCESS_CLEANUP_MINUTES",
        "default_minutes": 60,
    },
)


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    label = "ops"

    def ready(self) -> None:
        # post_migrate (not ready()) avoids DB queries on every manage.py command
        post_migrate.connect(make_sync_handler(MANAGED_SCHEDULES), sender=self)
        from django_q.models import Schedule

        pre_save.connect(
            make_restore_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="ops.protect_managed_q2_schedules",
        )
        post_delete.connect(
            make_recreate_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="ops.recreate_managed_q2_schedules",
        )
