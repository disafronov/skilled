"""Intake buffer layer — accumulates Telegram messages before Job creation."""

import logging

from django.db import transaction
from django.utils import timezone

from apps.bots.models import Bot
from apps.jobs.models import IntakeBuffer

logger = logging.getLogger(__name__)


def accept_telegram_message(
    bot: Bot,
    chat_id: str,
    message_id: int | None,
    text: str,
) -> IntakeBuffer:
    """Accumulate a Telegram message into the intake buffer for the given bot/chat.

    Both webhook and polling ingestion call this instead of creating Job directly.
    """
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
                last_message_at=timezone.now(),
            )
        else:
            buffer.text = "\n".join([buffer.text, text]) if buffer.text else text
            buffer.message_count += 1
            buffer.last_message_at = timezone.now()
            buffer.save(
                update_fields=["text", "message_count", "last_message_at", "updated_at"]
            )

        if message_id is not None:
            buffer.reply_to_message_id = message_id
            buffer.save(update_fields=["reply_to_message_id", "updated_at"])

    return buffer
