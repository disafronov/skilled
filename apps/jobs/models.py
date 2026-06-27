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

    def __str__(self) -> str:
        return f"Job #{self.pk} [{self.bot.name}]"
