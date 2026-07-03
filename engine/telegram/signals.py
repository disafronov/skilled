"""Signal-based orchestration for the Job pipeline."""

import logging
from collections.abc import Set as AbstractSet
from typing import Any

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from engine.telegram.models import Job

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
        logger.debug("Signal: job %d created — scheduling send_ack + worker", job_pk)
        # on_commit: the post_save signal fires inside the caller's atomic block.
        # Enqueuing Q2 tasks before the transaction commits would create orphan
        # tasks if the outer transaction rolls back.
        transaction.on_commit(
            lambda: async_task("engine.telegram.tasks.telegram_ack", job_pk)
        )
        transaction.on_commit(
            lambda: async_task("engine.processing.proxy.worker", job_pk)
        )
        return

    if (
        update_fields
        and "processing_finished_at" in update_fields
        and instance.processing_finished_at
    ):
        job_pk = instance.pk
        logger.debug(
            "Signal: job %d llm completed — scheduling telegram_deliver",
            job_pk,
        )
        transaction.on_commit(
            lambda: async_task("engine.telegram.tasks.telegram_deliver", job_pk)
        )
