from django import forms
from django.contrib import admin

from apps.inference.models import Profile, Provider, Worker
from engine.common.admin_forms import AdminModelForm
from engine.common.admin_mixins import CHANGES_FIELDSET


class ProviderAdminForm(AdminModelForm):
    masked_fields = ("auth_token",)

    class Meta:
        model = Provider
        fields = "__all__"
        widgets = {
            "base_url": forms.URLInput(),
        }
        labels = {
            "api_type": "API type",
            "base_url": "Base URL",
        }


class ProfileAdminForm(AdminModelForm):
    class Meta:
        model = Profile
        fields = "__all__"
        labels = {
            "top_p": "Top P",
        }


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    form = ProviderAdminForm
    fieldsets = (  # type: ignore[assignment]
        (
            None,
            {
                "fields": ("name", "api_type", "base_url", "auth_token"),
            },
        ),
        CHANGES_FIELDSET,
    )
    readonly_fields = ("updated_at", "created_at")
    list_display = ("name", "api_type", "base_url", "updated_at")
    search_fields = ["name"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    fieldsets = (  # type: ignore[assignment]
        (
            None,
            {
                "fields": (
                    "name",
                    "provider",
                    "model",
                    "temperature",
                    "top_p",
                    "max_output_tokens",
                    "reasoning_effort",
                    "response_format",
                ),
            },
        ),
        CHANGES_FIELDSET,
    )
    readonly_fields = ("updated_at", "created_at")
    list_display = (
        "name",
        "provider",
        "model",
        "temperature",
        "top_p",
        "max_output_tokens",
        "reasoning_effort",
        "updated_at",
    )
    list_select_related = ["provider"]
    search_fields = ["name", "provider__name"]
    list_filter = ["provider"]


class WorkerAdminForm(AdminModelForm):
    class Meta:
        model = Worker
        fields = "__all__"


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    form = WorkerAdminForm
    fieldsets = (  # type: ignore[assignment]
        (
            None,
            {
                "fields": (
                    "bot",
                    "profile",
                    "wrapper",
                    "enabled",
                ),
            },
        ),
        CHANGES_FIELDSET,
    )
    readonly_fields = ("created_at", "updated_at")
    list_display = (
        "bot",
        "profile",
        "wrapper",
        "enabled",
        "updated_at",
    )
    list_select_related = ["bot", "profile", "wrapper"]
    search_fields = ["bot__name"]
