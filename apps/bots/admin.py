from django.contrib import admin

from apps.admin_forms import MaskedFieldsAdminForm
from apps.bots.models import Bot


class BotAdminForm(MaskedFieldsAdminForm):
    masked_fields = ("telegram_api_token",)

    class Meta:
        model = Bot
        fields = "__all__"


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    form = BotAdminForm
    list_display = ["name", "skill", "wrapper", "profile", "created_at"]
    list_select_related = ["skill", "wrapper", "profile"]
    search_fields = ["name"]
