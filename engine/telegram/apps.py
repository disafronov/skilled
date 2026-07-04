"""AppConfig for engine.telegram — pipeline schedules (IDs 1–3)."""

from django.apps import AppConfig
from django.db.models.signals import post_delete, post_migrate, pre_save

from engine.common.schedules import (
    make_recreate_handler,
    make_restore_handler,
    make_sync_handler,
)

MANAGED_SCHEDULES = (
    {
        "id": 1,
        "name": "telegram_ingest",
        "func": "engine.telegram.tasks.telegram_ingest",
        "minutes": "Q2_TELEGRAM_INGEST_MINUTES",
    },
    {
        "id": 2,
        "name": "telegram_deliver",
        "func": "engine.telegram.tasks.telegram_deliver",
        "minutes": "Q2_TELEGRAM_DELIVER_MINUTES",
    },
    {
        "id": 3,
        "name": "telegram_intake_flush",
        "func": "engine.telegram.tasks.telegram_flush_intake_buffers",
        "minutes": "Q2_TELEGRAM_INTAKE_FLUSH_MINUTES",
    },
)


class TelegramConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine.telegram"
    label = "telegram"

    def ready(self) -> None:
        # post_migrate (not ready()) avoids DB queries on every manage.py command
        post_migrate.connect(
            make_sync_handler(MANAGED_SCHEDULES), sender=self, weak=False
        )
        from django_q.models import Schedule

        import engine.telegram.signals  # noqa: F401

        pre_save.connect(
            make_restore_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="telegram.protect_managed_q2_schedules",
            weak=False,
        )
        post_delete.connect(
            make_recreate_handler(MANAGED_SCHEDULES),
            sender=Schedule,
            dispatch_uid="telegram.recreate_managed_q2_schedules",
            weak=False,
        )
