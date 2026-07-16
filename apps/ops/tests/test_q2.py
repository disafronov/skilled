"""Tests for apps.ops.q2 module."""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from django_q.models import Task

from apps.ops.q2 import cleanup_q2_successes


class Q2SuccessCleanupTests(TestCase):
    """Test django-q2 successful task retention cleanup."""

    @override_settings(Q2_SUCCESS_RETENTION_SECONDS=60)
    def test_cleanup_deletes_only_expired_success_tasks(self):
        now = timezone.now()
        old = now - timedelta(seconds=120)
        fresh = now - timedelta(seconds=30)

        old_success = Task.objects.create(
            id="old_success",
            name="old_success",
            func="tests.task",
            started=old,
            stopped=old,
            success=True,
        )
        fresh_success = Task.objects.create(
            id="fresh_success",
            name="fresh_success",
            func="tests.task",
            started=fresh,
            stopped=fresh,
            success=True,
        )
        old_failure = Task.objects.create(
            id="old_failure",
            name="old_failure",
            func="tests.task",
            started=old,
            stopped=old,
            success=False,
        )

        cleanup_q2_successes()

        self.assertFalse(Task.objects.filter(id=old_success.id).exists())
        self.assertTrue(Task.objects.filter(id=fresh_success.id).exists())
        self.assertTrue(Task.objects.filter(id=old_failure.id).exists())
