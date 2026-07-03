"""django-q2 configuration and scheduled task functions."""

import os
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django_q.models import Success


def cleanup_q2_successes() -> None:
    """Delete successful django-q2 task records older than the retention window."""
    retention_seconds = int(
        os.environ.get(
            "Q2_SUCCESS_TASK_RETENTION_SECONDS",
            str(settings.Q2_SUCCESS_RETENTION_SECONDS),
        )
    )
    cutoff = timezone.now() - timedelta(seconds=retention_seconds)
    Success.objects.filter(stopped__lt=cutoff).delete()
