"""Signal-based orchestration for the Job pipeline."""

import logging
from collections.abc import Set as AbstractSet
from typing import Any

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from apps.jobs.models import Job

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Job)
def job_on_completion(
    sender: type[Job],
    instance: Job,
    created: bool,
    update_fields: AbstractSet[str] | None = None,
    **kwargs: Any,
) -> None:
    if created:
        job_pk = instance.pk
        logger.debug("Signal: job %d created — scheduling llm_worker", job_pk)
        transaction.on_commit(lambda: async_task("apps.jobs.tasks.llm_worker", job_pk))
        return

    if (
        update_fields
        and "llm_finished_at" in update_fields
        and instance.llm_finished_at
    ):
        job_pk = instance.pk
        logger.debug(
            "Signal: job %d llm completed — scheduling telegram_deliver",
            job_pk,
        )
        transaction.on_commit(
            lambda: async_task("apps.jobs.tasks.telegram_deliver", job_pk)
        )
