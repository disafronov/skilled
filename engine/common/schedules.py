"""Shared utilities for django-q2 schedule lifecycle management.

Apps that own managed schedules use these factory functions to wire up
pre_save/post_delete/post_migrate handlers without duplicating the core
logic.
"""

from collections.abc import Callable
from typing import Any

from django.conf import settings


def schedule_defaults(
    schedule: dict[str, Any],
    schedule_model: Any,
) -> dict[str, Any]:
    """Compute the authoritative field values for a managed schedule entry."""
    return {
        "name": schedule["name"],
        "func": schedule["func"],
        "hook": None,
        "args": None,
        "kwargs": None,
        "schedule_type": schedule_model.MINUTES,
        "minutes": getattr(settings, schedule["minutes"]),
        "cron": None,
        "cluster": None,
        "repeats": -1,
        "intended_date_kwarg": None,
    }


def _schedule_by_name(
    managed_schedules: tuple[dict[str, Any], ...],
) -> dict[str, dict[str, Any]]:
    """Index managed schedule definitions by their stable schedule name."""
    return {schedule["name"]: schedule for schedule in managed_schedules}


def make_restore_handler(
    managed_schedules: tuple[dict[str, Any], ...],
) -> Callable[[Any, Any], None]:
    """Return a pre_save handler that forces managed schedules back to code values.

    Admin edits would be lost on the next post_migrate anyway;
    this prevents accidental drift between post_migrate runs.
    """

    def _restore(sender: Any, instance: Any, **kwargs: Any) -> None:
        schedules_by_name = _schedule_by_name(managed_schedules)
        entry = schedules_by_name.get(instance.name)
        if entry is None and instance.pk:
            current_name = (
                sender.objects.filter(pk=instance.pk)
                .values_list("name", flat=True)
                .first()
            )
            entry = schedules_by_name.get(current_name)
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
        entry = _schedule_by_name(managed_schedules).get(instance.name)
        if entry is None:
            return

        from django_q.models import Schedule

        Schedule.objects.update_or_create(
            name=entry["name"],
            defaults=schedule_defaults(entry, Schedule),
        )

    return _recreate


def make_sync_handler(
    managed_schedules: tuple[dict[str, Any], ...],
) -> Callable[..., None]:
    """Return a post_migrate handler that creates/updates managed schedules.

    Removes any duplicate-named rows that have snuck in, then updates or creates
    the expected rows by stable schedule name instead of fixed primary keys.
    """

    def _sync(sender: Any, **kwargs: Any) -> None:
        # Lazy import to keep module-level imports cheap.
        from django_q.models import Schedule

        for entry in managed_schedules:
            defaults = schedule_defaults(entry, Schedule)
            schedules = list(Schedule.objects.filter(name=entry["name"]).order_by("id"))
            if not schedules:
                Schedule.objects.create(**defaults)
                continue

            canonical = schedules[0]
            Schedule.objects.filter(
                id__in=[schedule.id for schedule in schedules[1:]]
            ).delete()
            for field, value in defaults.items():
                setattr(canonical, field, value)
            canonical.save(update_fields=list(defaults.keys()))

    return _sync
