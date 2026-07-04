"""AppConfig for engine.proxy — Q2 schedule (ID 4)."""

from django.apps import AppConfig
from django.db.models.signals import post_delete, post_migrate, pre_save

from engine.common.schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
)

MANAGED_SCHEDULES = (
    {
        "id": 4,
        "name": "processing",
        "func": "engine.proxy.worker.worker",
        "minutes_env": "Q2_PROCESSING_MINUTES",
        "default_minutes": 1,
    },
)


class ProxyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine.proxy"
    label = "proxy"

    def ready(self) -> None:
        # post_migrate (not ready()) avoids DB queries on every manage.py command
        post_migrate.connect(
            make_sync_handler(MANAGED_SCHEDULES), sender=self, weak=False
        )

        from django_q.models import Schedule

        pre_save.connect(
            make_restore_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="proxy.protect_managed_q2_schedules",
            weak=False,
        )
        post_delete.connect(
            make_recreate_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="proxy.recreate_managed_q2_schedules",
            weak=False,
        )
