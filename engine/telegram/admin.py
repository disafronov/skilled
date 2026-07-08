from typing import Any

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.utils.text import Truncator
from django.utils.translation import ngettext
from django_q.tasks import async_task

from ..common.admin import CHANGES_FIELDSET, AdminModelForm
from .models import Bot, Job

JOB_PREVIEW_LENGTH = 80


def preview_text(value: str | None) -> str:
    if not value:
        return ""
    return Truncator(value).chars(JOB_PREVIEW_LENGTH)


class BotAdminForm(AdminModelForm):
    masked_fields = ("telegram_api_token",)

    class Meta:
        model = Bot
        exclude = ("webhook_secret",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    form = BotAdminForm
    fieldsets = (  # type: ignore[assignment]
        (
            None,
            {
                "fields": (
                    "name",
                    "telegram_api_token",
                    "enabled",
                    "telegram_update_offset",
                ),
            },
        ),
        (
            "Webhook",
            {
                "fields": (
                    "webhook_enabled_at",
                    "webhook_disabled_at",
                ),
            },
        ),
        CHANGES_FIELDSET,
    )
    readonly_fields = (
        "webhook_enabled_at",
        "webhook_disabled_at",
        "telegram_update_offset",
        "updated_at",
        "created_at",
    )
    list_display = (
        "name",
        "enabled",
        "telegram_update_offset",
        "webhook_enabled_at",
        "webhook_disabled_at",
        "updated_at",
    )
    list_select_related = ()
    search_fields = ["name"]
    actions = ["rotate_webhook_secret"]

    @admin.action(description="Rotate webhook secret for selected bots")
    def rotate_webhook_secret(
        self,
        request: Any,
        queryset: Any,
    ) -> None:
        """Regenerate webhook_secret and invalidate webhook registration."""
        count = 0
        for bot in queryset:
            bot.rotate_webhook_secret()
            count += 1
        self.message_user(
            request,
            ngettext(
                "Rotated webhook secret for %d bot",
                "Rotated webhook secret for %d bots",
                count,
            )
            % count,
            messages.SUCCESS,
        )


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    actions = ("retry_jobs", "retry_delivery_jobs")
    list_display = (
        "id",
        "bot",
        "reply_target",
        "reply_to_message_id",
        "raw_input_preview",
        "raw_output_preview",
        "processing_error_preview",
        "delivery_error_preview",
        "processing_started_at",
        "processing_finished_at",
        "delivery_started_at",
        "delivery_finished_at",
        "updated_at",
    )
    list_select_related = ["bot"]
    search_fields = ["raw_input", "processing_error", "delivery_error"]
    list_filter = (
        "created_at",
        "processing_started_at",
        "processing_finished_at",
        "delivery_started_at",
        "delivery_finished_at",
    )
    fieldsets = (  # type: ignore[assignment]
        (
            None,
            {
                "fields": (
                    "id",
                    "bot",
                    "reply_target",
                    "reply_to_message_id",
                    "raw_input",
                    "raw_output",
                    "processing_error",
                    "delivery_error",
                ),
            },
        ),
        (
            "Pipeline",
            {
                "fields": (
                    "processing_started_at",
                    "processing_finished_at",
                    "delivery_started_at",
                    "delivery_finished_at",
                ),
            },
        ),
        CHANGES_FIELDSET,
    )
    readonly_fields = (
        "id",
        "bot",
        "reply_target",
        "reply_to_message_id",
        "raw_input",
        "raw_output",
        "processing_error",
        "delivery_error",
        "processing_started_at",
        "processing_finished_at",
        "delivery_started_at",
        "delivery_finished_at",
        "updated_at",
        "created_at",
    )

    @admin.display(ordering="raw_input")
    def raw_input_preview(self, obj: Job) -> str:
        return preview_text(obj.raw_input)

    @admin.display(ordering="raw_output")
    def raw_output_preview(self, obj: Job) -> str:
        return preview_text(obj.raw_output)

    @admin.display(ordering="processing_error")
    def processing_error_preview(self, obj: Job) -> str:
        return preview_text(obj.processing_error)

    @admin.display(ordering="delivery_error")
    def delivery_error_preview(self, obj: Job) -> str:
        return preview_text(obj.delivery_error)

    @admin.action(description="Retry selected jobs")
    def retry_jobs(
        self,
        request: HttpRequest,
        queryset: QuerySet[Job],
    ) -> None:
        pks = list(queryset.values_list("pk", flat=True))
        count = Job.objects.filter(pk__in=pks).update(
            processing_started_at=None,
            processing_finished_at=None,
            raw_output=None,
            processing_error=None,
            delivery_error=None,
            delivery_started_at=None,
            delivery_finished_at=None,
            updated_at=timezone.now(),
        )
        for pk in pks:
            async_task(settings.Q2_PROCESSING_FUNC, pk)
        self.message_user(
            request,
            f"Retrying {count} job(s) for processing.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Retry selected delivery jobs")
    def retry_delivery_jobs(
        self,
        request: HttpRequest,
        queryset: QuerySet[Job],
    ) -> None:
        pks = list(queryset.values_list("pk", flat=True))
        count = Job.objects.filter(pk__in=pks).update(
            delivery_started_at=None,
            delivery_finished_at=None,
            delivery_error=None,
            updated_at=timezone.now(),
        )
        for pk in pks:
            async_task("engine.telegram.tasks.telegram_deliver", pk)
        self.message_user(
            request,
            f"Retrying {count} job(s) for delivery.",
            level=messages.SUCCESS,
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
