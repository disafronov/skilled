from typing import Any

from django.contrib import admin, messages
from django.utils.translation import ngettext

from apps.admin_forms import AdminModelForm
from apps.admin_mixins import CHANGES_FIELDSET
from apps.bots.models import Bot


class BotAdminForm(AdminModelForm):
    masked_fields = ("telegram_api_token",)

    class Meta:
        model = Bot
        exclude = ("webhook_secret",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["telegram_api_token"].label = "Telegram API credential"


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
                    "profile",
                    "wrapper",
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
        "updated_at",
        "created_at",
    )
    list_display = (
        "name",
        "profile",
        "wrapper",
        "enabled",
        "telegram_update_offset",
        "webhook_enabled_at",
        "webhook_disabled_at",
        "updated_at",
    )
    list_select_related = ["wrapper", "profile"]
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
