"""Management command: supervised launcher for qcluster + runserver (dev only)."""

import sys

from django.core.management.base import BaseCommand

from ..supervisor import _spawn, _supervise


class Command(BaseCommand):
    """Spawn qcluster and runserver as supervised children (development only)."""

    help = "Start qcluster and runserver together for local development"

    def handle(self, *args: object, **_options: object) -> None:
        """Launch child processes and hand off to the supervisor loop."""
        _supervise(
            [
                _spawn(sys.executable, "manage.py", "qcluster"),
                _spawn(sys.executable, "manage.py", "runserver", "0.0.0.0:8000"),
            ]
        )
