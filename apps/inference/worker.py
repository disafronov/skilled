"""LLM processing worker configured by ``Q2_PROCESSING_FUNC``."""

import logging

from django_telegram_q2.telegram.worker import Worker as BaseWorker

from apps.inference.client import call_llm
from apps.inference.models import Worker as WorkerModel

logger = logging.getLogger(__name__)


class LlmWorker(BaseWorker):
    """Process a Job via LLM call."""

    poll_filters = {"bot__worker__isnull": False, "bot__worker__enabled": True}
    poll_select_related: tuple[str, ...] = ()
    pk_select_related: tuple[str, ...] = ()

    def process(self, *, bot_id: int, raw_input: str) -> tuple[str | None, str | None]:
        try:
            wm = WorkerModel.objects.select_related(
                "profile__provider", "wrapper__skill"
            ).get(bot_id=bot_id)
        except WorkerModel.DoesNotExist:
            return None, "No worker configured for bot"

        if not wm.enabled:
            return None, f"Worker disabled for bot {bot_id}"

        logger.info("Processing job for bot %d", bot_id)
        result = call_llm(
            provider=wm.profile.provider,
            profile=wm.profile,
            skill=wm.wrapper.skill,
            wrapper=wm.wrapper,
            raw_input=raw_input,
        )
        return result, None
