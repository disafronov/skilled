"""Shared utilities for django-q2 schedule lifecycle management.

Apps that own managed schedules (engine.telegram, engine.processing,
apps.ops) use these factory functions to wire up
pre_save/post_delete/post_migrate handlers without duplicating the core
logic.
"""

import os
from collections.abc import Callable
from typing import Any

from django.core.management.color import no_style
from django.db import connection


def schedule_defaults(
    schedule: dict[str, Any],
    schedule_model: Any,
) -> dict[str, Any]:
    """Compute the authoritative field values for a managed schedule entry."""
    raw: str | None = os.environ.get(schedule["minutes_env"])
    return {
        "name": schedule["name"],
        "func": schedule["func"],
        "hook": None,
        "args": None,
        "kwargs": None,
        "schedule_type": schedule_model.MINUTES,
        "minutes": int(raw) if raw is not None else schedule["default_minutes"],
        "cron": None,
        "cluster": None,
        "repeats": -1,
        "intended_date_kwarg": None,
    }


def make_restore_handler(
    managed_schedules: tuple[dict[str, Any], ...],
) -> Callable[[Any, Any], None]:
    """Return a pre_save handler that forces managed schedules back to code values.

    Admin edits would be lost on the next post_migrate anyway;
    this prevents accidental drift between post_migrate runs.
    """

    def _restore(sender: Any, instance: Any, **kwargs: Any) -> None:
        schedules_by_id = {s["id"]: s for s in managed_schedules}
        entry = schedules_by_id.get(instance.pk)
        if entry is None:
            return
        for field, value in schedule_defaults(entry, sender).items():
            setattr(instance, field, value)

    return _restore


def make_recreate_handler(
    managed_schedules: tuple[dict[str, Any], ...],
) -> Callable[[Any, Any], None]:
    """Return a post_delete handler that recreates managed schedules.

    Post_delete (not pre_delete) allows the deletion to proceed, then
    immediately recreates the row with the canonical code-defined values.
    Safer than blocking the delete — no ProtectedError surprises.
    """

    def _recreate(sender: Any, instance: Any, **kwargs: Any) -> None:
        for entry in managed_schedules:
            if entry["id"] == instance.pk:
                from django_q.models import Schedule

                Schedule.objects.update_or_create(
                    id=entry["id"],
                    defaults=schedule_defaults(entry, Schedule),
                )
                break

    return _recreate


def make_sync_handler(
    managed_schedules: tuple[dict[str, Any], ...],
) -> Callable[..., None]:
    """Return a post_migrate handler that creates/updates managed schedules.

    Removes any duplicate-named rows that have snuck in, then updates
    or creates the expected rows at the canonical IDs.
    """

    def _sync(sender: Any, **kwargs: Any) -> None:
        # Lazy import to keep module-level imports cheap.
        from django_q.models import Schedule

        schedule_ids = [s["id"] for s in managed_schedules]
        schedule_names = [s["name"] for s in managed_schedules]

        Schedule.objects.filter(name__in=schedule_names).exclude(
            id__in=schedule_ids
        ).delete()

        for entry in managed_schedules:
            Schedule.objects.update_or_create(
                id=entry["id"],
                defaults=schedule_defaults(entry, Schedule),
            )

        with connection.cursor() as cursor:
            for sql in connection.ops.sequence_reset_sql(no_style(), [Schedule]):
                cursor.execute(sql)

    return _sync
