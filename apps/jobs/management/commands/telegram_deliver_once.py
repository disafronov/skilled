from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.jobs.models import Job
from workers.telegram import send_message


class Command(BaseCommand):
    help = 'Deliver completed LLM responses back to Telegram'

    def handle(self, *args, **options):
        jobs = Job.objects.filter(
            llm_finished_at__isnull=False,
            raw_output__isnull=False,
            sent_at__isnull=True,
            error__isnull=True,
        ).select_related('bot')

        delivered = 0
        for job in jobs:
            try:
                send_message(
                    token=job.bot.telegram_api_token,
                    chat_id=job.reply_target,
                    text=job.raw_output,
                )
                job.sent_at = timezone.now()
                job.save(update_fields=['sent_at'])
                delivered += 1
                self.stdout.write(f'Delivered Job #{job.pk}')
            except Exception as e:
                job.error = str(e)
                job.save(update_fields=['error'])
                self.stderr.write(f'Failed to deliver Job #{job.pk}: {e}')

        self.stdout.write(f'Delivered {delivered} message(s)')
