from django.contrib import admin

from apps.bots.models import Bot


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ["name", "skill", "wrapper", "profile", "created_at"]
    list_select_related = ["skill", "wrapper", "profile"]
    search_fields = ["name"]
