from django.db import models

from apps.common.fields import EncryptedCharField


class Bot(models.Model):
    """Telegram bot endpoint — ties an LLM profile + wrapper to a Telegram API token."""

    name = models.CharField(max_length=255, unique=True)
    telegram_api_token = EncryptedCharField(max_length=512)

    profile = models.ForeignKey(
        "inference.Profile",
        on_delete=models.PROTECT,
    )
    wrapper = models.ForeignKey(
        "library.Wrapper",
        on_delete=models.PROTECT,
    )

    enabled = models.BooleanField(
        default=True, help_text="Is this bot active for message processing?"
    )
    telegram_update_offset = models.IntegerField(
        default=0,
        help_text="Last processed Telegram update_id",
    )
    webhook_enabled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the webhook was last successfully registered",
    )
    webhook_disabled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the webhook was last disabled (fallback to polling)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Bot"
        verbose_name_plural = "Bots"

    def __str__(self) -> str:
        return self.name
