"""Q2-callable task functions for the core pipeline."""

import logging
import os
from collections import defaultdict
from datetime import timedelta
from typing import NotRequired, TypedDict, cast

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_q.models import Success

from apps.bots.models import Bot
from apps.jobs.models import Job
from workers.llm import call_llm
from workers.telegram import (
    delete_webhook,
    detect_document_format,
    document_format_content_type,
    document_format_filename,
    get_updates,
    get_webhook_info,
    sanitize_error,
    send_document,
    send_message,
    set_webhook,
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


def _manage_webhook_for_bot(bot: Bot) -> bool:
    """Check webhook health and register / heal / fallback. Returns True if healthy."""
    # Respect cooldown — skip API calls entirely if recently fell back
    if bot.webhook_disabled_at:
        elapsed = (timezone.now() - bot.webhook_disabled_at).total_seconds()
        if elapsed < settings.WEBHOOK_COOLDOWN_SECONDS:
            return False

    try:
        info = get_webhook_info(bot.telegram_api_token)
    except RuntimeError:
        return False

    expected_url = f"{settings.BASE_URL}/webhook/"
    current_url = info.get("url", "")
    pending = info.get("pending_update_count", 0)
    last_error = info.get("last_error_message")

    is_healthy = (
        current_url == expected_url
        and pending < settings.WEBHOOK_FALLBACK_PENDING_THRESHOLD
        and not last_error
    )

    if is_healthy:
        if not bot.webhook_enabled_at or bot.webhook_disabled_at:
            Bot.objects.filter(pk=bot.pk).update(
                webhook_enabled_at=timezone.now(),
                webhook_disabled_at=None,
            )
        return True

    # Register or fix webhook
    if current_url != expected_url or last_error:
        try:
            set_webhook(
                bot.telegram_api_token,
                expected_url,
                secret_token=bot.webhook_secret,
            )
            Bot.objects.filter(pk=bot.pk).update(
                webhook_enabled_at=timezone.now(),
                webhook_disabled_at=None,
            )
            return True
        except RuntimeError:
            logger.warning(
                "Bot %s: failed to register webhook, falling back to polling",
                bot.id,
            )

    # Fall back to polling
    try:
        delete_webhook(bot.telegram_api_token)
    except RuntimeError:
        pass
    Bot.objects.filter(pk=bot.pk).update(
        webhook_disabled_at=timezone.now(),
    )
    return False


def telegram_ack(job_id: int) -> None:
    """Send queue acknowledgement to the user who sent the message."""
    job = Job.objects.select_related("bot").filter(pk=job_id).first()
    if job is None:
        logger.warning("telegram_ack: job %d not found", job_id)
        return
    try:
        send_message(
            job.bot.telegram_api_token,
            job.reply_target,
            QUEUE_ACK_TEXT,
            reply_to_message_id=job.reply_to_message_id,
        )
    except Exception as exc:
        logger.error(
            "telegram_ack: job %d failed: %s", job_id, exc, exc_info=settings.DEBUG
        )


def telegram_ingest() -> None:
    """Poll Telegram for updates and manage webhook lifecycle."""
    try:
        # Clean up webhooks for disabled bots.
        # Done here rather than on Bot.save to avoid adding Telegram API calls
        # to the admin save flow. The periodic ingest cycle handles it naturally.
        for bot in Bot.objects.filter(enabled=False, webhook_enabled_at__isnull=False):
            try:
                delete_webhook(bot.telegram_api_token)
            except RuntimeError:
                logger.warning("Bot %s: failed to delete webhook", bot.id)
                continue
            Bot.objects.filter(pk=bot.pk).update(webhook_enabled_at=None)

        for bot in Bot.objects.filter(enabled=True):
            try:
                # Webhook management (if BASE_URL configured)
                if settings.BASE_URL:
                    webhook_active = _manage_webhook_for_bot(bot)
                    if webhook_active:
                        continue

                # Lightweight lock on the Bot row: skip_locked=True avoids
                # queueing behind another worker already processing this bot.
                with transaction.atomic():
                    locked = (
                        Bot.objects.select_for_update(skip_locked=True)
                        .filter(pk=bot.pk)
                        .first()
                    )
                    if locked is None:
                        continue
                    offset = locked.telegram_update_offset or None

                updates = cast(
                    list[_TelegramUpdate],
                    get_updates(locked.telegram_api_token, offset=offset),
                )
                if not updates:
                    continue

                logger.debug("Bot %s: processing %d updates", locked.id, len(updates))

                max_id = locked.telegram_update_offset or 0
                for u in updates:
                    max_id = max(max_id, int(u["update_id"]))

                if (
                    locked.telegram_update_offset
                    and max_id <= locked.telegram_update_offset
                ):
                    continue

                message_batches: dict[str, _MessageBatch] = defaultdict(
                    lambda: {"messages": [], "reply_to_message_id": None}
                )
                for update in updates:
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

                # Offset gate + job creation + offset advance in one atomic block.
                # The second select_for_update re-reads the Bot row (now locked with
                # no skip_locked) to verify the offset hasn't been claimed by another
                # worker between the first lock and get_updates.
                with transaction.atomic():
                    current = (
                        Bot.objects.select_for_update().filter(pk=locked.pk).first()
                    )
                    if current is None:
                        continue
                    if (
                        current.telegram_update_offset is not None
                        and max_id <= current.telegram_update_offset
                    ):
                        continue

                    for chat_id, batch in message_batches.items():
                        messages = batch["messages"]
                        message_id = batch["reply_to_message_id"]
                        Job.objects.create(
                            bot=current,
                            reply_target=chat_id,
                            reply_to_message_id=message_id,
                            raw_input=" ".join(messages),
                        )

                    if message_batches:
                        logger.info(
                            "Bot %s: created %d job(s) from %d update(s)",
                            current.id,
                            len(message_batches),
                            len(updates),
                            exc_info=settings.DEBUG,
                        )

                    new_offset = max_id + 1
                    current.telegram_update_offset = new_offset
                    current.save(update_fields=["telegram_update_offset", "updated_at"])

            except Exception as e:
                logger.error(
                    "Bot %s ingest failed: %s", bot.id, e, exc_info=settings.DEBUG
                )
    except Exception as e:
        logger.critical(
            "telegram_ingest global failure: %s", e, exc_info=settings.DEBUG
        )


def llm_worker(job_pk: int | None = None) -> None:
    """Process a Job via LLM (signal or poll-driven)."""
    with transaction.atomic():
        if job_pk is not None:
            try:
                job = (
                    Job.objects.select_for_update(skip_locked=True)
                    .select_related(
                        "bot__wrapper__skill",
                        "bot__profile__provider",
                    )
                    .get(pk=job_pk)
                )
            except Job.DoesNotExist:
                logger.warning("llm_worker: job %d does not exist", job_pk)
                return
            if job.llm_finished_at is not None:
                logger.debug("llm_worker: job %d already processed, skipping", job_pk)
                return
        else:
            stale_seconds = int(
                os.environ.get(
                    "Q2_LLM_STALE_JOB_SECONDS",
                    str(Q2_LLM_STALE_JOB_SECONDS),
                )
            )
            stale_cutoff = timezone.now() - timedelta(seconds=stale_seconds)
            Job.objects.select_for_update(skip_locked=True).stale_llm(
                stale_cutoff
            ).update(llm_started_at=None, updated_at=timezone.now())

            next_job = (
                Job.objects.select_for_update(skip_locked=True)
                .ready_for_llm()
                .select_related(
                    "bot__wrapper__skill",
                    "bot__profile__provider",
                )
                .order_by("created_at", "id")
                .first()
            )
            if next_job is None:
                return
            job = next_job

        job.llm_started_at = timezone.now()
        job.save(update_fields=["llm_started_at", "updated_at"])

    try:
        bot = job.bot
        logger.info("LLM worker: processing job %d for bot %d", job.pk, bot.pk)
        raw_output = call_llm(
            provider=bot.profile.provider,
            profile=bot.profile,
            skill=bot.wrapper.skill,
            wrapper=bot.wrapper,
            raw_input=job.raw_input,
        )
        job.raw_output = raw_output
        logger.info("LLM worker: job %d completed (%d chars)", job.pk, len(raw_output))
    except Exception as exc:
        logger.error(
            "LLM worker: job %d failed: %s", job.pk, exc, exc_info=settings.DEBUG
        )
        job.llm_finished_at = timezone.now()
        job.error = sanitize_error(str(exc))
        job.save(update_fields=["raw_output", "llm_finished_at", "error", "updated_at"])
        raise

    job.llm_finished_at = timezone.now()
    job.save(update_fields=["raw_output", "error", "llm_finished_at", "updated_at"])


def telegram_deliver(job_pk: int | None = None) -> None:
    """Deliver a completed Job response to Telegram (signal or poll-driven)."""
    with transaction.atomic():
        if job_pk is not None:
            try:
                job = (
                    Job.objects.select_for_update(skip_locked=True)
                    .select_related("bot")
                    .get(pk=job_pk)
                )
            except Job.DoesNotExist:
                logger.warning("telegram_deliver: job %d does not exist", job_pk)
                return
            if job.delivery_finished_at is not None:
                logger.debug(
                    "telegram_deliver: job %d already delivered, skipping", job_pk
                )
                return
        else:
            next_job = (
                Job.objects.select_for_update(skip_locked=True)
                .ready_for_delivery()
                .select_related("bot")
                .order_by("llm_finished_at", "id")
                .first()
            )
            if not next_job:
                return
            job = next_job

        job.delivery_started_at = timezone.now()
        job.save(update_fields=["delivery_started_at", "updated_at"])

    try:
        if job.error:
            logger.info(
                "Delivery: job %d — sending error to chat %s", job.pk, job.reply_target
            )
            send_message(
                job.bot.telegram_api_token,
                job.reply_target,
                job.error,
                reply_to_message_id=job.reply_to_message_id,
            )
        else:
            logger.info(
                "Delivery: job %d — sending response to chat %s (%d chars)",
                job.pk,
                job.reply_target,
                len(job.raw_output or ""),
            )
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
        logger.info("Delivery: job %d completed", job.pk)
    except Exception as exc:
        logger.error(
            "Delivery: job %d failed: %s", job.pk, exc, exc_info=settings.DEBUG
        )
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
