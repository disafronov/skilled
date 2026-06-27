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
    def __init__(self, manager, filtered_kwargs):
        self.manager = manager
        self.filtered_kwargs = filtered_kwargs

    def update(self, **kwargs):
        self.manager.update_calls.append((self.filtered_kwargs, kwargs))


class JobManagerStub:
    def __init__(self):
        self.update_calls = []

    def filter(self, **kwargs):
        return JobQuerySetStub(self, kwargs)


class MigrationTests(TestCase):
    def test_backfill_job_state_for_constraints(self):
        manager = JobManagerStub()
        job_model = type("JobStub", (), {"objects": manager})
        apps = AppsStub(job_model)

        migration.backfill_job_state_for_constraints(apps, None)

        self.assertEqual(len(manager.update_calls), 3)
        self.assertEqual(
            manager.update_calls[0],
            (
                {
                    "sent_at__isnull": False,
                    "raw_output__isnull": True,
                },
                {"raw_output": ""},
            ),
        )
        self.assertEqual(
            manager.update_calls[1],
            (
                {
                    "sent_at__isnull": True,
                    "llm_finished_at__isnull": False,
                    "raw_output__isnull": True,
                    "error__isnull": True,
                },
                {"error": migration.MISSING_LLM_RESULT_ERROR},
            ),
        )
        filtered_kwargs, updated_fields = manager.update_calls[2]
        self.assertEqual(
            filtered_kwargs,
            {
                "sent_at__isnull": False,
                "delivery_started_at__isnull": True,
            },
        )
        delivery_started_at = updated_fields["delivery_started_at"]
        self.assertIsInstance(delivery_started_at, models.F)
        self.assertEqual(delivery_started_at.name, "sent_at")
