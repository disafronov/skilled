"""django-q2 configuration and scheduled task functions."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django_q.models import Success


def cleanup_q2_successes() -> None:
    """Delete successful django-q2 task records older than the retention window.

    The retention window comes from the ``Q2_SUCCESS_RETENTION_SECONDS`` Django
    setting, which itself is sourced from the ``Q2_SUCCESS_RETENTION_SECONDS``
    environment variable in ``config/settings.py``.
    """
    cutoff = timezone.now() - timedelta(seconds=settings.Q2_SUCCESS_RETENTION_SECONDS)
    Success.objects.filter(stopped__lt=cutoff).delete()
