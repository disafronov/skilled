from django.db import models


class Skill(models.Model):
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
    name = models.CharField(max_length=255, unique=True)
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Wrapper"
        verbose_name_plural = "Wrappers"

    def __str__(self) -> str:
        return self.name
