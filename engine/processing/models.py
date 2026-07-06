"""Abstract base class for processing pipeline workers.

Subclasses implement business logic in :meth:`process`; everything else
— Job selection, transaction management, error handling — lives here.
"""

from __future__ import annotations

import abc
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from engine.common.sanitize import sanitize_error
from engine.telegram.models import Job

logger = logging.getLogger(__name__)


class Worker(abc.ABC):
    """Base processing worker.

    Subclasses override :meth:`process` (the business logic) and optionally
    set class attributes to control Job selection:

    * ``poll_filters`` — keyword arguments passed to ``.filter()`` in
      poll mode (e.g. ``{"bot__worker__enabled": True}``).
    * ``poll_select_related`` — relation paths to preload in poll mode.
    * ``pk_select_related`` — relation paths to preload in pk mode.

    Multiple subclasses may exist; the active worker is selected by the
    configured task function (``settings.Q2_PROCESSING_FUNC``).
    """

    poll_filters: dict = {}
    poll_select_related: tuple[str, ...] = ()
    pk_select_related: tuple[str, ...] = ()

    def run(self, job_pk: int | None = None) -> None:
        """Main entry point — select a Job, run process(), save result."""
        with transaction.atomic():
            job = self._get_job(job_pk)
            if job is None:
                return
            job.processing_started_at = timezone.now()
            job.save(update_fields=["processing_started_at", "updated_at"])

        try:
            raw_output, error = self.process(bot_id=job.bot_id, raw_input=job.raw_input)
        except Exception as exc:
            logger.error(
                "Worker %s: job %d failed",
                type(self).__name__,
                job.pk,
                exc_info=settings.DEBUG,
            )
            self._save_result(job, None, str(exc))
            raise
        self._save_result(job, raw_output, error)

    def _get_job(self, job_pk: int | None) -> Job | None:
        """Return the next Job to process, or ``None``."""
        if job_pk is not None:
            return self._get_job_by_pk(job_pk)
        return self._poll_next_job()

    def _get_job_by_pk(self, job_pk: int) -> Job | None:
        """Fetch a specific Job by primary key."""
        try:
            job = (
                Job.objects.select_for_update(skip_locked=True)
                .select_related("bot", *self.pk_select_related)
                .get(pk=job_pk)
            )
        except Job.DoesNotExist:
            logger.warning(
                "Worker %s: job %d does not exist", type(self).__name__, job_pk
            )
            return None
        if job.processing_finished_at is not None:
            logger.debug(
                "Worker %s: job %d already processed, skipping",
                type(self).__name__,
                job_pk,
            )
            return None
        return job

    def _poll_next_job(self) -> Job | None:
        """Find the next pending Job (poll mode)."""
        self._reset_stale_jobs()
        qs = Job.objects.select_for_update(skip_locked=True)
        if self.poll_filters:
            qs = qs.filter(**self.poll_filters)
        if self.poll_select_related:
            qs = qs.select_related(*self.poll_select_related)
        return qs.ready_for_processing().order_by("created_at", "id").first()

    def _reset_stale_jobs(self) -> None:
        """Unstick Jobs that were claimed but never finished."""
        stale_cutoff = timezone.now() - timedelta(
            seconds=settings.Q2_PROCESSING_STALE_JOB_SECONDS
        )
        Job.objects.select_for_update(skip_locked=True).stale_processing(
            stale_cutoff
        ).update(processing_started_at=None, updated_at=timezone.now())

    def _save_result(self, job: Job, raw_output: str | None, error: str | None) -> None:
        """Persist the processing outcome on *job*."""
        if error is not None:
            job.error = sanitize_error(error)
            job.processing_finished_at = timezone.now()
            job.save(update_fields=["error", "processing_finished_at", "updated_at"])
            return

        if (
            raw_output is not None
        ):  # pragma: no branch — both-None blocked by db constraint
            logger.info(
                "Worker %s: job %d completed (%d chars)",
                type(self).__name__,
                job.pk,
                len(raw_output),
            )

        job.raw_output = raw_output
        job.processing_finished_at = timezone.now()
        job.save(
            update_fields=[
                "raw_output",
                "error",
                "processing_finished_at",
                "updated_at",
            ]
        )

    @abc.abstractmethod
    def process(self, *, bot_id: int, raw_input: str) -> tuple[str | None, str | None]:
        """Business logic — return ``(raw_output, error)``.

        Subclasses receive the minimum required data (``bot_id``, ``raw_input``)
        rather than the full ``Job`` model, keeping the engine boundary clean.

        Return ``(result, None)`` on success.
        Return ``(None, error_message)`` on handled error (no re-raise).
        Raise an exception on unexpected failure (re-raised by :meth:`run`).
        """
