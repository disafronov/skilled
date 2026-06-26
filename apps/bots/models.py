from django.db import models


class Bot(models.Model):
    name = models.CharField(max_length=255, unique=True)
    telegram_api_token = models.CharField(max_length=255)

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Bot"
        verbose_name_plural = "Bots"

    def __str__(self) -> str:
        return self.name
