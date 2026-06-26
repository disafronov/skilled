"""Q2-callable task functions for the core pipeline."""

import logging
import os
from datetime import timedelta
from typing import Any, cast

from django.db import transaction
from django.utils import timezone
from django_q.models import Success

from apps.bots.models import Bot
from apps.jobs.models import Job
from workers.llm import call_llm
from workers.telegram import (
    detect_document_format,
    document_format_content_type,
    document_format_filename,
    get_updates,
    send_document,
    send_message,
)

logger = logging.getLogger(__name__)

QUEUE_ACK_TEXT = "Added to the processing queue, please wait..."
Q2_SUCCESS_RETENTION_SECONDS = 86400
LLM_STALE_JOB_SECONDS = 3600


def telegram_ingest() -> None:
    """Poll Telegram for updates and create Job records."""
    try:
        for bot in Bot.objects.filter(enabled=True):
            try:
                acknowledgements = []
                with transaction.atomic():
                    offset = bot.telegram_update_offset or None
                    updates = get_updates(bot.telegram_api_token, offset=offset)
                    if not updates:
                        continue

                    max_id = bot.telegram_update_offset or 0
                    message_batches: dict[str, dict[str, Any]] = {}
                    for update in updates:
                        update_id = int(cast(Any, update["update_id"]))
                        max_id = max(max_id, update_id)

                        message = cast(dict[str, Any] | None, update.get("message"))
                        if not message:
                            continue

                        text = message.get("text")
                        if not isinstance(text, str):
                            continue

                        text = text.strip()
                        if not text or text.startswith("/"):
                            continue

                        chat_id = str(message["chat"]["id"])
                        message_id = message.get("message_id")
                        batch = message_batches.setdefault(
                            chat_id,
                            {"messages": [], "reply_to_message_id": None},
                        )
                        cast(list[str], batch["messages"]).append(text)
                        batch["reply_to_message_id"] = message_id

                    jobs_to_create = []
                    for chat_id, batch in message_batches.items():
                        messages = cast(list[str], batch["messages"])
                        message_id = cast(int | None, batch["reply_to_message_id"])
                        jobs_to_create.append(
                            Job(
                                bot=bot,
                                reply_target=chat_id,
                                reply_to_message_id=message_id,
                                raw_input=" ".join(messages),
                                received_at=timezone.now(),
                            )
                        )
                        acknowledgements.append((chat_id, message_id))

                    if jobs_to_create:
                        Job.objects.bulk_create(jobs_to_create)

                    new_offset = max_id + 1
                    bot.telegram_update_offset = new_offset
                    bot.save(update_fields=["telegram_update_offset", "updated_at"])

                for chat_id, message_id in acknowledgements:
                    try:
                        send_message(
                            bot.telegram_api_token,
                            chat_id,
                            QUEUE_ACK_TEXT,
                            reply_to_message_id=message_id,
                        )
                    except Exception as exc:
                        logger.error(
                            f"Bot {bot.id} queue acknowledgement failed: {exc}",
                            exc_info=True,
                        )

            except Exception as e:
                logger.error(f"Bot {bot.id} ingest failed: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"telegram_ingest global failure: {e}", exc_info=True)


def llm_worker() -> None:
    """Process one pending Job via LLM."""
    try:
        with transaction.atomic():
            stale_seconds = int(
                os.environ.get(
                    "LLM_STALE_JOB_SECONDS",
                    str(LLM_STALE_JOB_SECONDS),
                )
            )
            stale_cutoff = timezone.now() - timedelta(seconds=stale_seconds)
            Job.objects.select_for_update(skip_locked=True).filter(
                received_at__isnull=False,
                llm_started_at__lt=stale_cutoff,
                llm_finished_at__isnull=True,
                error__isnull=True,
            ).update(llm_started_at=None, updated_at=timezone.now())

            job = (
                Job.objects.select_for_update(skip_locked=True)
                .filter(
                    received_at__isnull=False,
                    llm_started_at__isnull=True,
                    error__isnull=True,
                )
                .select_related(
                    "bot__wrapper__skill",
                    "bot__profile__provider",
                )
                .first()
            )
            if job is None:
                return

            job.llm_started_at = timezone.now()
            job.save(update_fields=["llm_started_at", "updated_at"])

        try:
            bot = job.bot
            raw_output = call_llm(
                provider=bot.profile.provider,
                profile=bot.profile,
                skill=bot.wrapper.skill,
                wrapper=bot.wrapper,
                raw_input=job.raw_input,
            )
            job.raw_output = raw_output
        except Exception as exc:
            job.error = str(exc)
        finally:
            job.llm_finished_at = timezone.now()
            job.save(
                update_fields=["raw_output", "error", "llm_finished_at", "updated_at"]
            )
    except Exception as e:
        logger.error(f"llm_worker failed: {e}", exc_info=True)


def telegram_deliver() -> None:
    """Deliver one completed Job response to Telegram."""
    try:
        with transaction.atomic():
            job = (
                Job.objects.select_for_update(skip_locked=True)
                .filter(
                    llm_finished_at__isnull=False,
                    raw_output__isnull=False,
                    sent_at__isnull=True,
                    error__isnull=True,
                )
                .select_related("bot")
                .first()
            )
            if not job:
                return

        try:
            raw_output = job.raw_output or ""
            document_format = detect_document_format(raw_output)
            send_document(
                job.bot.telegram_api_token,
                job.reply_target,
                raw_output,
                document_format_filename(job.pk, document_format),
                document_format_content_type(document_format),
                caption="LLM response is attached as a text file.",
                reply_to_message_id=job.reply_to_message_id,
            )
            job.sent_at = timezone.now()
        except Exception as exc:
            job.error = str(exc)

        job.save(update_fields=["sent_at", "error", "updated_at"])
    except Exception as e:
        logger.error(f"telegram_deliver failed: {e}", exc_info=True)


def cleanup_q2_successes() -> None:
    """Delete successful django-q2 task records older than the retention window."""
    retention_seconds = int(
        os.environ.get(
            "Q2_SUCCESS_TASK_RETENTION_SECONDS",
            str(Q2_SUCCESS_RETENTION_SECONDS),
        )
    )
    cutoff = timezone.now() - timedelta(seconds=retention_seconds)
    Success.objects.filter(stopped__lt=cutoff).delete()
