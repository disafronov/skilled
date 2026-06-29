"""Q2-callable task functions for the core pipeline."""

import logging
import os
from collections import defaultdict
from datetime import timedelta
from typing import NotRequired, TypedDict, cast

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
    sanitize_error,
    send_document,
    send_message,
)

logger = logging.getLogger(__name__)

QUEUE_ACK_TEXT = "Added to the processing queue, please wait..."
Q2_SUCCESS_RETENTION_SECONDS = 86400
Q2_LLM_STALE_JOB_SECONDS = 3600


class _TelegramChat(TypedDict):
    id: int


class _TelegramMessage(TypedDict):
    chat: _TelegramChat
    text: NotRequired[str]
    message_id: NotRequired[int]


class _TelegramUpdate(TypedDict):
    update_id: int
    message: NotRequired[_TelegramMessage]


class _MessageBatch(TypedDict):
    messages: list[str]
    reply_to_message_id: int | None


def telegram_ingest() -> None:
    """Poll Telegram for updates and create Job records."""
    try:
        for bot in Bot.objects.filter(enabled=True):
            try:
                offset = bot.telegram_update_offset or None
                updates = cast(
                    list[_TelegramUpdate],
                    get_updates(bot.telegram_api_token, offset=offset),
                )
                if not updates:
                    continue

                max_id = bot.telegram_update_offset or 0
                message_batches: dict[str, _MessageBatch] = defaultdict(
                    lambda: {"messages": [], "reply_to_message_id": None}
                )
                for update in updates:
                    update_id = int(update["update_id"])
                    max_id = max(max_id, update_id)

                    message = update.get("message")
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
                    batch = message_batches[chat_id]
                    batch["messages"].append(text)
                    batch["reply_to_message_id"] = message_id

                acknowledgements: list[tuple[str, int | None]] = []
                jobs_to_create = []
                for chat_id, batch in message_batches.items():
                    messages = batch["messages"]
                    message_id = batch["reply_to_message_id"]
                    jobs_to_create.append(
                        Job(
                            bot=bot,
                            reply_target=chat_id,
                            reply_to_message_id=message_id,
                            raw_input=" ".join(messages),
                        )
                    )
                    acknowledgements.append((chat_id, message_id))

                with transaction.atomic():
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
                            "Bot %s queue acknowledgement failed: %s",
                            bot.id,
                            exc,
                            exc_info=True,
                        )

            except Exception as e:
                logger.error("Bot %s ingest failed: %s", bot.id, e, exc_info=True)
    except Exception as e:
        logger.critical("telegram_ingest global failure: %s", e, exc_info=True)


def llm_worker() -> None:
    """Process one pending Job via LLM."""
    with transaction.atomic():
        stale_seconds = int(
            os.environ.get(
                "Q2_LLM_STALE_JOB_SECONDS",
                str(Q2_LLM_STALE_JOB_SECONDS),
            )
        )
        stale_cutoff = timezone.now() - timedelta(seconds=stale_seconds)
        Job.objects.select_for_update(skip_locked=True).stale_llm(stale_cutoff).update(
            llm_started_at=None, updated_at=timezone.now()
        )

        job = (
            Job.objects.select_for_update(skip_locked=True)
            .ready_for_llm()
            .select_related(
                "bot__wrapper__skill",
                "bot__profile__provider",
            )
            .order_by("created_at", "id")
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
        job.llm_finished_at = timezone.now()
        job.error = sanitize_error(str(exc))
        job.save(update_fields=["raw_output", "llm_finished_at", "error", "updated_at"])
        raise

    job.llm_finished_at = timezone.now()
    job.save(update_fields=["raw_output", "error", "llm_finished_at", "updated_at"])


def telegram_deliver() -> None:
    """Deliver one completed Job response to Telegram."""
    with transaction.atomic():
        job = (
            Job.objects.select_for_update(skip_locked=True)
            .ready_for_delivery()
            .select_related("bot")
            .order_by("llm_finished_at", "id")
            .first()
        )
        if not job:
            return

        job.delivery_started_at = timezone.now()
        job.save(update_fields=["delivery_started_at", "updated_at"])

    try:
        if job.error:
            send_message(
                job.bot.telegram_api_token,
                job.reply_target,
                job.error,
                reply_to_message_id=job.reply_to_message_id,
            )
        else:
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
        job.delivery_finished_at = timezone.now()
    except Exception as exc:
        job.error = sanitize_error(str(exc))
        job.save(update_fields=["error", "updated_at"])
        raise

    job.save(update_fields=["delivery_finished_at", "error", "updated_at"])


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
