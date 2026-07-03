"""LLM processing worker — single subclass of engine.processing.Worker."""

import logging

from apps.llm.models import Worker as WorkerModel
from apps.workers.llm import call_llm
from engine.processing import Worker as BaseWorker
from engine.telegram.models import Job

logger = logging.getLogger(__name__)


class LlmWorker(BaseWorker):
    """Process a Job via LLM call.

    Single Worker subclass (singleton enforced by ``__init_subclass__``).
    """

    poll_filters = {"bot__worker__isnull": False, "bot__worker__enabled": True}
    poll_select_related: tuple[str, ...] = ()
    pk_select_related: tuple[str, ...] = ()

    def process(self, job: Job) -> tuple[str | None, str | None]:
        try:
            wm = WorkerModel.objects.select_related(
                "profile__provider", "wrapper__skill"
            ).get(bot=job.bot)
        except WorkerModel.DoesNotExist:
            return None, "No worker configured for bot"

        if not wm.enabled:
            return None, f"Worker disabled for bot {job.bot.pk}"

        logger.info("Processing job %d for bot %d", job.pk, job.bot.pk)
        result = call_llm(
            provider=wm.profile.provider,
            profile=wm.profile,
            skill=wm.wrapper.skill,
            wrapper=wm.wrapper,
            raw_input=job.raw_input,
        )
        return result, None
