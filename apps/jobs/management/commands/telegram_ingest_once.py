"""Management command: poll Telegram for updates and create Job records."""

from django.core.management.base import BaseCommand

from apps.jobs.tasks import telegram_ingest


class Command(BaseCommand):
    help = "Poll Telegram for updates and create Job records"

    def handle(self, *args, **options):
        telegram_ingest()
