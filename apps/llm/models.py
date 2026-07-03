"""Worker model — execution configuration for a bot."""

from django.db import models


class Worker(models.Model):
    """Bot execution config — links to LLM profile and prompt wrapper."""

    bot = models.OneToOneField(
        "telegram.Bot",
        on_delete=models.CASCADE,
        related_name="worker",
    )
    profile = models.ForeignKey(
        "inference.Profile",
        on_delete=models.PROTECT,
    )
    wrapper = models.ForeignKey(
        "library.Wrapper",
        on_delete=models.PROTECT,
    )
    enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["bot__name"]
        verbose_name = "Worker"
        verbose_name_plural = "Workers"
        db_table = "llm_worker"

    def __str__(self) -> str:
        return f"Worker for {self.bot.name}"
