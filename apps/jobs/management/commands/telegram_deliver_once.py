"""Management command: deliver one completed Job response to Telegram."""

from django.core.management.base import BaseCommand

from apps.jobs.tasks import telegram_deliver


class Command(BaseCommand):
    help = "Deliver one completed Job response to Telegram"

    def handle(self, *args: str, **_options: str) -> None:
        telegram_deliver()
