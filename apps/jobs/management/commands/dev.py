"""Management command: supervised launcher for qcluster + runserver (dev only)."""

import subprocess  # nosec B404 — fixed args, no shell, no user input
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from ..supervisor import _supervise


class Command(BaseCommand):
    """Spawn qcluster and runserver as supervised children (development only)."""

    help = "Start qcluster and runserver together for local development"

    def handle(self, *args: object, **_options: object) -> None:
        """Launch child processes and hand off to the supervisor loop."""
        _supervise(
            [
                subprocess.Popen(  # nosec B603 — fixed args, no user input
                    [sys.executable, "manage.py", "qcluster"],
                    cwd=settings.BASE_DIR,
                ),
                subprocess.Popen(  # nosec B603 — fixed args, no user input
                    [sys.executable, "manage.py", "runserver", "0.0.0.0:8000"],
                    cwd=settings.BASE_DIR,
                ),
            ]
        )
