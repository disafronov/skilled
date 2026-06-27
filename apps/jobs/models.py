from datetime import datetime

from django.db import models


class JobQuerySet(models.QuerySet["Job"]):
    def stale_llm(self, cutoff: datetime) -> "JobQuerySet":
        return self.filter(
            llm_started_at__lt=cutoff,
            llm_finished_at__isnull=True,
            error__isnull=True,
        )

    def ready_for_llm(self) -> "JobQuerySet":
        return self.filter(
            llm_started_at__isnull=True,
            llm_finished_at__isnull=True,
            error__isnull=True,
        )

    def ready_for_delivery(self) -> "JobQuerySet":
        return self.filter(
            llm_finished_at__isnull=False,
            delivery_started_at__isnull=True,
            delivery_finished_at__isnull=True,
        ).exclude(raw_output__isnull=True, error__isnull=True)


class Job(models.Model):
    bot = models.ForeignKey("bots.Bot", on_delete=models.PROTECT)
    reply_target = models.TextField()
    reply_to_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    raw_input = models.TextField()
    raw_output = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    llm_started_at = models.DateTimeField(null=True, blank=True)
    llm_finished_at = models.DateTimeField(null=True, blank=True)
    delivery_started_at = models.DateTimeField(null=True, blank=True)
    delivery_finished_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Job"
        verbose_name_plural = "Jobs"
        indexes = [
            models.Index(
                fields=["created_at", "id"],
                name="job_ready_llm_idx",
                condition=models.Q(
                    llm_started_at__isnull=True,
                    llm_finished_at__isnull=True,
                    error__isnull=True,
                ),
            ),
            models.Index(
                fields=["llm_started_at"],
                name="job_stale_llm_idx",
                condition=models.Q(
                    llm_started_at__isnull=False,
                    llm_finished_at__isnull=True,
                    error__isnull=True,
                ),
            ),
            models.Index(
                fields=["-created_at", "id"],
                name="job_ready_delivery_idx",
                condition=models.Q(
                    llm_finished_at__isnull=False,
                    raw_output__isnull=False,
                    delivery_finished_at__isnull=True,
                    error__isnull=True,
                ),
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(raw_output__isnull=True)
                    | models.Q(llm_finished_at__isnull=False)
                ),
                name="job_raw_output_requires_llm_finished",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(llm_finished_at__isnull=True)
                    | models.Q(raw_output__isnull=False)
                    | models.Q(error__isnull=False)
                ),
                name="job_llm_finished_requires_result_or_error",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(delivery_started_at__isnull=True)
                    | (
                        models.Q(llm_finished_at__isnull=False)
                        & (
                            models.Q(raw_output__isnull=False)
                            | models.Q(error__isnull=False)
                        )
                    )
                ),
                name="job_delivery_started_requires_output",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(delivery_finished_at__isnull=True)
                    | models.Q(delivery_started_at__isnull=False)
                ),
                name="job_delivery_finished_requires_started",
            ),
        ]

    def __str__(self) -> str:
        return f"Job #{self.pk} [{self.bot.name}]"
