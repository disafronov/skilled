from django import forms
from django.contrib import admin

from apps.admin_forms import AdminModelForm
from apps.inference.models import Profile, Provider


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
    fields = ("name", "api_type", "base_url", "auth_token", "updated_at", "created_at")
    readonly_fields = ("updated_at", "created_at")
    list_display = ("name", "api_type", "base_url", "updated_at")
    search_fields = ["name"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    fields = (
        "name",
        "provider",
        "model",
        "temperature",
        "top_p",
        "max_output_tokens",
        "reasoning_effort",
        "response_format",
        "updated_at",
        "created_at",
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
