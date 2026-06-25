from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import Job
from workers.llm import call_llm


class Command(BaseCommand):
    help = "Process one pending Job and call LLM"

    def handle(self, *args: object, **options: object) -> None:
        with transaction.atomic():
            job = (
                Job.objects.select_for_update(skip_locked=True)
                .filter(
                    received_at__isnull=False,
                    llm_started_at__isnull=True,
                    error__isnull=True,
                )
                .select_related(
                    "bot__skill",
                    "bot__wrapper",
                    "bot__provider",
                    "bot__profile",
                )
                .first()
            )

            if job is None:
                self.stdout.write("No pending jobs")
                return

            job.llm_started_at = timezone.now()
            job.save(update_fields=["llm_started_at"])

        # Transaction commits here — LLM call happens outside the lock
        try:
            bot = job.bot
            result = call_llm(
                provider=bot.provider,
                profile=bot.profile,
                skill=bot.skill,
                wrapper=bot.wrapper,
                raw_input=job.raw_input,
            )
            job.raw_output = result
            job.llm_finished_at = timezone.now()
            job.save(update_fields=["raw_output", "llm_finished_at"])
            self.stdout.write(f"Job #{job.pk} completed")
        except Exception as e:
            job.error = str(e)
            job.llm_finished_at = timezone.now()
            job.save(update_fields=["error", "llm_finished_at"])
            self.stderr.write(f"Job #{job.pk} failed: {e}")
