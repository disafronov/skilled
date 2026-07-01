"""Webhook views for bot message ingestion."""

import json
import logging

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.bots.models import Bot
from apps.jobs.intake import accept_telegram_message

logger = logging.getLogger(__name__)

_SECRET_TOKEN_HEADER = (
    "HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN"  # nosec — header name, not a secret value
)


@csrf_exempt
@require_POST
def webhook(request: HttpRequest) -> HttpResponse:
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

    secret = request.META.get(_SECRET_TOKEN_HEADER)
    if not secret:
        logger.info("Webhook: missing secret token header")
        return HttpResponse("not found", status=404)

    bot = Bot.objects.filter(enabled=True, webhook_secret=secret).first()

    if bot is None:
        logger.info("Webhook: unverified request")
        return HttpResponse("not found", status=404)

    chat_id = str(message["chat"]["id"])
    message_id = message.get("message_id")
    message_date = int(message["date"])
    accept_telegram_message(bot, chat_id, message_id, message_date, text)
    return HttpResponse("ok")
