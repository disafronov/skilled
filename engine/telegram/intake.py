"""Intake buffer layer — accumulates Telegram messages before Job creation."""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_q.tasks import schedule

from engine.telegram.models import Bot, IntakeBuffer, Job

logger = logging.getLogger(__name__)


def accept_telegram_message(
    bot: Bot,
    chat_id: str,
    message_id: int | None,
    message_date: int,
    text: str,
) -> IntakeBuffer:
    """Accumulate a Telegram message into the intake buffer for the given bot/chat.

    Groups consecutive messages within TELEGRAM_INTAKE_DEBOUNCE_SECONDS
    into one buffer. Messages beyond the interval trigger an immediate
    flush of the old buffer into a Job before creating a new buffer.
    """
    debounce = getattr(settings, "TELEGRAM_INTAKE_DEBOUNCE_SECONDS", 10)

    with transaction.atomic():
        buffer = (
            IntakeBuffer.objects.select_for_update()
            .filter(bot=bot, chat_id=chat_id, flushed_at__isnull=True)
            .first()
        )

        if buffer is None:
            buffer = IntakeBuffer.objects.create(
                bot=bot,
                chat_id=chat_id,
                text=text,
                message_count=1,
                reply_to_message_id=message_id,
                last_message_ts=message_date,
                last_received_at=timezone.now(),
            )
        elif message_date - buffer.last_message_ts <= debounce:
            buffer.text = "\n".join([buffer.text, text]) if buffer.text else text
            buffer.message_count += 1
            buffer.last_message_ts = message_date
            buffer.last_received_at = timezone.now()
            buffer.save(
                update_fields=(
                    "text",
                    "message_count",
                    "last_message_ts",
                    "last_received_at",
                )
            )
        else:
            _flush_intake(buffer)
            buffer = IntakeBuffer.objects.create(
                bot=bot,
                chat_id=chat_id,
                text=text,
                message_count=1,
                reply_to_message_id=message_id,
                last_message_ts=message_date,
                last_received_at=timezone.now(),
            )

    from django_q.models import Schedule as QSchedule

    # q2's schedule() has incomplete stubs — mypy cannot infer the lambda arg type
    transaction.on_commit(
        lambda pk=buffer.pk: schedule(  # type: ignore[misc]
            "engine.telegram.tasks._flush_due_buffer",
            pk,
            schedule_type=QSchedule.ONCE,
            next_run=timezone.now() + timedelta(seconds=debounce),
        )
    )

    return buffer


def _flush_intake(buffer: IntakeBuffer) -> None:
    """Close the buffer and create a Job from its accumulated text."""
    Job.objects.create(
        bot=buffer.bot,
        reply_target=str(buffer.chat_id),
        reply_to_message_id=buffer.reply_to_message_id,
        raw_input=buffer.text,
    )
    buffer.flushed_at = timezone.now()
    buffer.save(update_fields=("flushed_at",))
