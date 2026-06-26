from typing import Any

from django.contrib import admin

from apps.admin_forms import (
    AdminModelForm,
    model_admin_fields,
    model_admin_list_display,
)
from apps.bots.models import Bot


class BotAdminForm(AdminModelForm):
    masked_fields = ("telegram_api_token",)

    class Meta:
        model = Bot
        fields = "__all__"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["telegram_api_token"].label = "Telegram API credential"


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    form = BotAdminForm
    fields = model_admin_fields(Bot)
    readonly_fields = ("updated_at", "created_at")
    list_display = model_admin_list_display(
        Bot,
        exclude=("telegram_api_token",),
    )
    list_select_related = ["wrapper", "profile"]
    search_fields = ["name"]
