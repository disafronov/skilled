from django.db import models
from django_telegram_q2.common.fields import EncryptedCharField


class ApiType(models.TextChoices):
    """Supported LLM API protocol types."""

    OPENAI = "openai", "OpenAI Compatible"


class Provider(models.Model):
    """LLM API provider configuration (endpoint URL + auth token)."""

    name = models.CharField(max_length=255, unique=True)
    api_type = models.CharField(
        max_length=32,
        choices=ApiType.choices,
        default=ApiType.OPENAI,
    )
    base_url = models.URLField()
    auth_token = EncryptedCharField(max_length=8192)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Provider"
        verbose_name_plural = "Providers"

    def __str__(self) -> str:
        return self.name


class Profile(models.Model):
    """LLM model profile — model name, parameters, and provider link."""

    name = models.CharField(max_length=255)
    provider = models.ForeignKey(
        Provider,
        on_delete=models.PROTECT,
        related_name="profiles",
    )

    model = models.CharField(max_length=255)
    temperature = models.FloatField(null=True, blank=True)
    top_p = models.FloatField(null=True, blank=True)
    max_output_tokens = models.IntegerField(null=True, blank=True)
    reasoning_effort = models.CharField(max_length=64, null=True, blank=True)
    response_format = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "name"],
                name="unique_profile_name_per_provider",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Worker(models.Model):
    """Bot execution config — links to LLM profile and prompt wrapper."""

    bot = models.OneToOneField(
        "telegram.Bot",
        on_delete=models.CASCADE,
        related_name="worker",
    )
    profile = models.ForeignKey(
        Profile,
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
        db_table = "inference_worker"

    def __str__(self) -> str:
        return f"Worker for {self.bot.name}"
