from django.db import models


class Bot(models.Model):
    name = models.CharField(max_length=255, unique=True)
    telegram_api_token = models.CharField(max_length=255)

    provider = models.ForeignKey(
        "inference.Provider",
        on_delete=models.PROTECT,
    )
    profile = models.ForeignKey(
        "inference.Profile",
        on_delete=models.PROTECT,
    )
    skill = models.ForeignKey(
        "library.Skill",
        on_delete=models.PROTECT,
    )
    wrapper = models.ForeignKey(
        "library.Wrapper",
        on_delete=models.PROTECT,
    )

    enabled = models.BooleanField(
        default=True, help_text="Is this bot active for message processing?"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Bot"
        verbose_name_plural = "Bots"

    def __str__(self) -> str:
        return self.name
