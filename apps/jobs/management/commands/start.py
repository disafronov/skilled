"""Management command: supervised launcher for qcluster + gunicorn."""

import sys

from django.core.management.base import BaseCommand

from ..supervisor import _spawn, _supervise


class Command(BaseCommand):
    """Spawn qcluster and gunicorn under a common supervisor."""

    help = "Start qcluster and gunicorn under a common supervisor"

    def handle(self, *args: object, **_options: object) -> None:
        """Launch child processes and hand off to the supervisor loop."""
        _supervise(
            [
                _spawn(sys.executable, "manage.py", "qcluster"),
                _spawn("gunicorn", "config.wsgi"),
            ]
        )
