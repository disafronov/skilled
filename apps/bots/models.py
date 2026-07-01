import secrets

from django.db import models

from apps.common.fields import EncryptedCharField


def generate_webhook_secret() -> str:
    """Generate a 32-char hex string for X-Telegram-Bot-Api-Secret-Token."""
    return secrets.token_hex(16)


class Bot(models.Model):
    """Telegram bot endpoint — ties an LLM profile + wrapper to a Telegram API token."""

    name = models.CharField(max_length=255, unique=True)
    telegram_api_token = EncryptedCharField(max_length=512)

    webhook_secret = EncryptedCharField(
        max_length=64,
        default=generate_webhook_secret,
        help_text="Secret token sent as X-Telegram-Bot-Api-Secret-Token header",
    )

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

    def rotate_webhook_secret(self) -> None:
        """Generate a new webhook_secret and invalidate current webhook registration."""
        type(self).objects.filter(pk=self.pk).update(
            webhook_secret=generate_webhook_secret(),
            webhook_enabled_at=None,
        )
