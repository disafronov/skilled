from django.db import models


class Skill(models.Model):
    """System-level instruction content used as the system prompt for the LLM."""

    name = models.CharField(max_length=255, unique=True)
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Skill"
        verbose_name_plural = "Skills"

    def __str__(self) -> str:
        return self.name


class Wrapper(models.Model):
    """Per-bot wrapper instruction content, combined with the skill for the LLM."""

    name = models.CharField(max_length=255)
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="wrappers",
    )
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Wrapper"
        verbose_name_plural = "Wrappers"
        constraints = [
            models.UniqueConstraint(
                fields=["skill", "name"],
                name="unique_wrapper_name_per_skill",
            )
        ]

    def __str__(self) -> str:
        return self.name
