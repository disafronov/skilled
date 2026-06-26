from django.db import models


class ApiType(models.TextChoices):
    OPENAI = "openai", "OpenAI Compatible"


class Provider(models.Model):
    name = models.CharField(max_length=255, unique=True)
    api_type = models.CharField(
        max_length=32,
        choices=ApiType.choices,
        default=ApiType.OPENAI,
    )
    base_url = models.URLField()
    auth_token = models.CharField(max_length=4096)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Provider"
        verbose_name_plural = "Providers"

    def __str__(self) -> str:
        return self.name


class Profile(models.Model):
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
