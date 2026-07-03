from django.contrib import admin

from apps.llm.models import Worker


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    """Admin for execution configuration."""

    list_display = (
        "bot",
        "profile",
        "wrapper",
        "enabled",
        "updated_at",
    )
    list_select_related = ("bot", "profile", "wrapper")
    search_fields = ("bot__name",)
    readonly_fields = ("created_at", "updated_at")
