from django.contrib import admin
from django.http import HttpRequest
from django.utils.text import Truncator

from apps.admin_forms import model_admin_fields, model_admin_list_display
from apps.jobs.models import Job

JOB_PREVIEW_LENGTH = 80


def preview_text(value: str | None) -> str:
    if not value:
        return ""
    return Truncator(value).chars(JOB_PREVIEW_LENGTH)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = model_admin_list_display(
        Job,
        include_pk=True,
        replacements={
            "raw_input": "raw_input_preview",
            "raw_output": "raw_output_preview",
            "error": "error_preview",
        },
    )
    list_select_related = ("bot",)
    search_fields = ("raw_input",)
    list_filter = (
        "created_at",
        "llm_started_at",
        "llm_finished_at",
        "delivery_started_at",
        "sent_at",
    )
    fields = model_admin_fields(Job, include_pk=True)
    readonly_fields = fields

    @admin.display(description="Raw input", ordering="raw_input")
    def raw_input_preview(self, obj: Job) -> str:
        return preview_text(obj.raw_input)

    @admin.display(description="Raw output", ordering="raw_output")
    def raw_output_preview(self, obj: Job) -> str:
        return preview_text(obj.raw_output)

    @admin.display(description="Error", ordering="error")
    def error_preview(self, obj: Job) -> str:
        return preview_text(obj.error)

    # Prevent create, edit, delete
    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        obj: Job | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        _request: HttpRequest,
        obj: Job | None = None,
    ) -> bool:
        return False
