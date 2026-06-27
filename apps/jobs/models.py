from django.db import models


class Job(models.Model):
    bot = models.ForeignKey("bots.Bot", on_delete=models.PROTECT)
    reply_target = models.TextField()
    reply_to_message_id = models.PositiveBigIntegerField(null=True, blank=True)
    raw_input = models.TextField()
    raw_output = models.TextField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)

    llm_started_at = models.DateTimeField(null=True, blank=True)
    llm_finished_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
                    sent_at__isnull=True,
                    error__isnull=True,
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"Job #{self.pk} [{self.bot.name}]"
