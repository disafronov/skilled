"""Management command: process one pending Job via LLM."""

from django.core.management.base import BaseCommand

from apps.jobs.tasks import llm_worker


class Command(BaseCommand):
    help = "Process one pending Job via LLM"

    def handle(self, *args: str, **_options: str) -> None:
        llm_worker()
