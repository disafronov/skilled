"""Q2-callable task functions for the core pipeline."""

import logging

from django.db import transaction
from django.utils import timezone

from apps.bots.models import Bot
from apps.jobs.models import Job
from workers.llm import call_llm
from workers.telegram import TELEGRAM_MESSAGE_CHAR_LIMIT, get_updates, send_document
from workers.telegram import send_message

logger = logging.getLogger(__name__)

QUEUE_ACK_TEXT = "Added to the processing queue, please wait..."


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
                    jobs_to_create = []
                    for update in updates:
                        message = update.get("message")
                        if not message:
                            continue
                        max_id = max(max_id, update["update_id"])
                        chat_id = message["chat"]["id"]
                        message_id = message.get("message_id")
                        text = message.get("text", "")
                        jobs_to_create.append(
                            Job(
                                bot=bot,
                                reply_target=str(chat_id),
                                reply_to_message_id=message_id,
                                raw_input=text,
                                received_at=timezone.now(),
                            )
                        )
                        acknowledgements.append((str(chat_id), message_id))

                    if jobs_to_create:
                        Job.objects.bulk_create(jobs_to_create)

                    new_offset = max_id + 1
                    bot.telegram_update_offset = new_offset
                    bot.save(update_fields=["telegram_update_offset"])

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
            job = (
                Job.objects.select_for_update(skip_locked=True)
                .filter(
                    received_at__isnull=False,
                    llm_started_at__isnull=True,
                    error__isnull=True,
                )
                .select_related(
                    "bot__skill",
                    "bot__wrapper",
                    "bot__provider",
                    "bot__profile",
                )
                .first()
            )
            if job is None:
                return

            job.llm_started_at = timezone.now()
            job.save(update_fields=["llm_started_at"])

        # Transaction commits here — LLM call happens outside the lock
        try:
            bot = job.bot
            raw_output = call_llm(
                provider=bot.provider,
                profile=bot.profile,
                skill=bot.skill,
                wrapper=bot.wrapper,
                raw_input=job.raw_input,
            )
            job.raw_output = raw_output
        except Exception as exc:
            job.error = str(exc)
        finally:
            job.llm_finished_at = timezone.now()
            job.save(update_fields=["raw_output", "error", "llm_finished_at"])
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
                .first()
            )
            if not job:
                return

            try:
                if len(job.raw_output) <= TELEGRAM_MESSAGE_CHAR_LIMIT:
                    send_message(
                        job.bot.telegram_api_token,
                        job.reply_target,
                        job.raw_output,
                        reply_to_message_id=job.reply_to_message_id,
                    )
                else:
                    send_document(
                        job.bot.telegram_api_token,
                        job.reply_target,
                        job.raw_output,
                        f"response-{job.pk}.md",
                        caption="LLM response is attached as a text file.",
                        reply_to_message_id=job.reply_to_message_id,
                    )
                job.sent_at = timezone.now()
            except Exception as exc:
                job.error = str(exc)

            job.save(update_fields=["sent_at", "error"])
    except Exception as e:
        logger.error(f"telegram_deliver failed: {e}", exc_info=True)
