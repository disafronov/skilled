from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
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
    actions = ("retry_llm_jobs", "retry_delivery_jobs")
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
        "delivery_finished_at",
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

    @admin.action(description="Retry selected LLM jobs")
    def retry_llm_jobs(
        self,
        request: HttpRequest,
        queryset: QuerySet[Job],
    ) -> None:
        updated = queryset.filter(
            llm_finished_at__isnull=True,
            delivery_started_at__isnull=True,
            delivery_finished_at__isnull=True,
        ).update(
            llm_started_at=None,
            llm_finished_at=None,
            raw_output=None,
            error=None,
            delivery_started_at=None,
            delivery_finished_at=None,
            updated_at=timezone.now(),
        )
        if updated:
            self.message_user(
                request,
                f"Queued {updated} job(s) for LLM retry.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No selected jobs were eligible for LLM retry.",
                level=messages.WARNING,
            )

    @admin.action(description="Retry selected delivery jobs")
    def retry_delivery_jobs(
        self,
        request: HttpRequest,
        queryset: QuerySet[Job],
    ) -> None:
        updated = queryset.filter(
            llm_finished_at__isnull=False,
            delivery_finished_at__isnull=True,
        ).update(
            delivery_started_at=None,
            delivery_finished_at=None,
            error=None,
            updated_at=timezone.now(),
        )
        if updated:
            self.message_user(
                request,
                f"Queued {updated} job(s) for delivery retry.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No selected jobs were eligible for delivery retry.",
                level=messages.WARNING,
            )

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
