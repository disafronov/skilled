"""Management command: deliver one completed Job response to Telegram."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import Job
from workers.telegram import send_message


class Command(BaseCommand):
    help = "Deliver one completed Job response to Telegram"

    def handle(self, *args, **options):
        with transaction.atomic():
            job = (
                Job.objects
                .select_for_update(skip_locked=True)
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
                send_message(
                    job.bot.telegram_api_token,
                    job.reply_target,
                    job.raw_output,
                )
                job.sent_at = timezone.now()
            except Exception as exc:
                job.error = str(exc)

            job.save(update_fields=["sent_at", "error"])
