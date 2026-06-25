"""Management command: supervised launcher for qcluster + gunicorn."""

import subprocess  # nosec B404 — fixed args, no shell, no user input
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from ..supervisor import _supervise


class Command(BaseCommand):
    """Spawn qcluster and gunicorn under a common supervisor."""

    help = "Start qcluster and gunicorn under a common supervisor"

    def handle(self, *args: object, **options: object) -> None:
        """Launch child processes and hand off to the supervisor loop."""
        _supervise(
            [
                subprocess.Popen(  # nosec B603 — fixed args, no user input
                    [sys.executable, "manage.py", "qcluster"],
                    cwd=settings.BASE_DIR,
                ),
                subprocess.Popen(  # nosec B603 B607 — fixed args, no user input
                    ["gunicorn", "config.wsgi"],
                    cwd=settings.BASE_DIR,
                ),
            ]
        )
