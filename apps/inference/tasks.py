"""Worker task — LLM pipeline processing via LlmWorker."""

from apps.inference.worker import LlmWorker


def worker(job_pk: int | None = None) -> None:
    """Process a Job via LLM (signal or poll-driven).

    Thin wrapper around :class:`LlmWorker`.
    """
    LlmWorker().run(job_pk)
