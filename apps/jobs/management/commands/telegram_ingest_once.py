import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.bots.models import Bot
from apps.jobs.models import Job
from workers.telegram import get_updates


class Command(BaseCommand):
    help = 'Poll Telegram for messages and create Job records'

    def handle(self, *args, **options):
        for bot in Bot.objects.all():
            self._process_bot(bot)

    def _process_bot(self, bot: Bot) -> None:
        self.stdout.write(f'Polling bot: {bot.name}')
        try:
            updates = get_updates(bot.telegram_api_token)
        except Exception as e:
            self.stderr.write(f'Failed to poll bot {bot.name}: {e}')
            return

        for update in updates.get('result', []):
            update_id = update.get('update_id')
            message = update.get('message')
            if not message:
                continue

            chat_id = str(message['chat']['id'])
            text = message.get('text', '')

            if not text:
                continue

            job = Job.objects.create(
                bot=bot,
                reply_target=chat_id,
                raw_input=text,
                received_at=timezone.now(),
            )
            self.stdout.write(f'  Created Job #{job.pk} for chat {chat_id}')

            # Mark update as processed by tracking offset
            # We store last processed update_id as bot state
            self._save_offset(bot, update_id + 1)

    def _save_offset(self, bot: Bot, offset: int) -> None:
        pass
