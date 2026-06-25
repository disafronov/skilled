"""Management command: poll Telegram for updates and create Job records."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.bots.models import Bot
from apps.jobs.models import Job
from workers.telegram import get_updates


class Command(BaseCommand):
    help = "Poll Telegram for updates and create Job records"

    def handle(self, *args, **options):
        for bot in Bot.objects.filter(enabled=True):
            offset = bot.telegram_update_offset or None
            updates = get_updates(bot.telegram_api_token, offset=offset)
            if not updates:
                continue

            max_id = bot.telegram_update_offset
            for update in updates:
                message = update.get("message")
                if not message:
                    continue
                chat_id = message["chat"]["id"]
                reply_target = str(chat_id)
                raw_input = message.get("text", "")
                Job.objects.create(
                    bot=bot,
                    reply_target=reply_target,
                    raw_input=raw_input,
                    received_at=timezone.now(),
                )
                max_id = max(max_id, update["update_id"])

            bot.telegram_update_offset = max_id + 1
            bot.save(update_fields=["telegram_update_offset"])
