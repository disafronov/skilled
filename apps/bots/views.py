"""Webhook views for bot message ingestion."""

import json
import logging

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.bots.models import Bot
from apps.common.fields import encrypt_deterministic
from apps.jobs.models import Job

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def webhook(request: HttpRequest, token: str) -> HttpResponse:
    """Receive Telegram update via webhook and enqueue it as a Job."""
    try:
        body = json.loads(request.body)
    except ValueError, UnicodeDecodeError:
        logger.warning("Webhook: invalid JSON body")
        return HttpResponse("invalid json", status=400)

    message = body.get("message")
    if not message:
        return HttpResponse("ok")

    text = message.get("text")
    if not isinstance(text, str):
        return HttpResponse("ok")

    text = text.strip()
    if not text or text.startswith("/"):
        return HttpResponse("ok")

    try:
        encrypted = encrypt_deterministic(token)
    except RuntimeError:
        logger.error("Webhook: FIELD_ENCRYPTION_KEY not configured")
        return HttpResponse("encryption error", status=500)

    # AES-SIV ciphertext is raw bytes; Django's ORM would run it through
    # get_prep_value → EncryptedCharField.get_prep_value, which encrypts again.
    # Use .extra() with raw SQL to compare the already-encrypted value directly.
    bot = (
        Bot.objects.filter(enabled=True)
        .extra(
            where=["telegram_api_token = %s"],
            params=[encrypted],
        )
        .first()
    )

    if bot is None:
        logger.info("Webhook: bot not found")
        return HttpResponse("not found", status=404)

    chat_id = str(message["chat"]["id"])
    message_id = message.get("message_id")

    Job.objects.create(
        bot=bot,
        reply_target=chat_id,
        reply_to_message_id=message_id,
        raw_input=text,
    )

    return HttpResponse("ok")
