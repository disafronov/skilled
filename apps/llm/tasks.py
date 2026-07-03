"""Worker task — LLM pipeline processing."""

import logging
import os
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.llm.models import Worker as WorkerModel
from apps.workers.llm import call_llm
from engine.common.sanitize import sanitize_error
from engine.telegram.models import Job

logger = logging.getLogger(__name__)
Q2_PROCESSING_STALE_JOB_SECONDS = 3600


def worker(job_pk: int | None = None) -> None:
    """Process a Job via LLM (signal or poll-driven)."""
    with transaction.atomic():
        if job_pk is not None:
            try:
                job = (
                    Job.objects.select_for_update(skip_locked=True)
                    .select_related("bot")
                    .get(pk=job_pk)
                )
            except Job.DoesNotExist:
                logger.warning("worker: job %d does not exist", job_pk)
                return
            if job.processing_finished_at is not None:
                logger.debug("worker: job %d already processed, skipping", job_pk)
                return
        else:
            stale_seconds = int(
                os.environ.get(
                    "Q2_PROCESSING_STALE_JOB_SECONDS",
                    str(Q2_PROCESSING_STALE_JOB_SECONDS),
                )
            )
            stale_cutoff = timezone.now() - timedelta(seconds=stale_seconds)
            Job.objects.select_for_update(skip_locked=True).stale_processing(
                stale_cutoff
            ).update(processing_started_at=None, updated_at=timezone.now())

            next_job = (
                Job.objects.select_for_update(skip_locked=True)
                .ready_for_processing()
                .filter(
                    bot__worker__isnull=False,
                    bot__worker__enabled=True,
                )
                .select_related(
                    "bot__worker__wrapper__skill",
                    "bot__worker__profile__provider",
                )
                .order_by("created_at", "id")
                .first()
            )
            if next_job is None:
                return
            job = next_job

        job.processing_started_at = timezone.now()
        job.save(update_fields=["processing_started_at", "updated_at"])

    bot = job.bot
    try:
        if job_pk is not None:
            w = WorkerModel.objects.select_related(
                "profile__provider", "wrapper__skill"
            ).get(bot=bot)
        else:
            w = bot.worker

        if not w.enabled:
            raise RuntimeError(f"Worker disabled for bot {bot.pk}")

        logger.info("Worker: processing job %d for bot %d", job.pk, bot.pk)
        raw_output = call_llm(
            provider=w.profile.provider,
            profile=w.profile,
            skill=w.wrapper.skill,
            wrapper=w.wrapper,
            raw_input=job.raw_input,
        )
        job.raw_output = raw_output
        logger.info("Worker: job %d completed (%d chars)", job.pk, len(raw_output))
    except WorkerModel.DoesNotExist:
        logger.error("Worker: no worker for bot %d", bot.pk)
        job.processing_finished_at = timezone.now()
        job.error = sanitize_error("No worker configured for bot")
        job.save(update_fields=["processing_finished_at", "error", "updated_at"])
    except Exception as exc:
        logger.error("Worker: job %d failed: %s", job.pk, exc, exc_info=settings.DEBUG)
        job.processing_finished_at = timezone.now()
        job.error = sanitize_error(str(exc))
        job.save(
            update_fields=[
                "raw_output",
                "processing_finished_at",
                "error",
                "updated_at",
            ]
        )
        raise

    job.processing_finished_at = timezone.now()
    job.save(
        update_fields=["raw_output", "error", "processing_finished_at", "updated_at"]
    )
