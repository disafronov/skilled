from django.contrib import admin

from apps.jobs.models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bot",
        "reply_target",
        "raw_input",
        "raw_output",
        "error",
        "received_at",
        "llm_started_at",
        "llm_finished_at",
        "sent_at",
    )
    list_select_related = ("bot",)
    search_fields = ("raw_input",)
    list_filter = ("received_at", "llm_started_at", "llm_finished_at", "sent_at")
    readonly_fields = (
        "bot",
        "reply_target",
        "raw_input",
        "raw_output",
        "error",
        "received_at",
        "llm_started_at",
        "llm_finished_at",
        "sent_at",
        "created_at",
        "updated_at",
    )

    # Prevent create, edit, delete
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
