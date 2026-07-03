"""AppConfig for engine.processing — processing pipeline foundation."""

from django.apps import AppConfig


class ProcessingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine.processing"
    label = "processing"
