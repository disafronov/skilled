import importlib
from unittest import TestCase

from django.db import models

migration = importlib.import_module(
    "apps.jobs.migrations.0006_backfill_delivery_started_at_and_job_constraints"
)


class AppsStub:
    def __init__(self, job_model):
        self.job_model = job_model

    def get_model(self, app_label, model_name):
        if (app_label, model_name) == ("jobs", "Job"):
            return self.job_model
        raise LookupError(app_label, model_name)


class JobQuerySetStub:
    def __init__(self):
        self.updated_fields = None

    def update(self, **kwargs):
        self.updated_fields = kwargs


class JobManagerStub:
    def __init__(self):
        self.filtered_kwargs = None
        self.queryset = JobQuerySetStub()

    def filter(self, **kwargs):
        self.filtered_kwargs = kwargs
        return self.queryset


class MigrationTests(TestCase):
    def test_backfill_delivery_started_at_uses_sent_at(self):
        manager = JobManagerStub()
        job_model = type("JobStub", (), {"objects": manager})
        apps = AppsStub(job_model)

        migration.backfill_delivery_started_at(apps, None)

        self.assertEqual(
            manager.filtered_kwargs,
            {
                "sent_at__isnull": False,
                "delivery_started_at__isnull": True,
            },
        )
        delivery_started_at = manager.queryset.updated_fields["delivery_started_at"]
        self.assertIsInstance(delivery_started_at, models.F)
        self.assertEqual(delivery_started_at.name, "sent_at")
