from django import forms
from django.contrib import admin

from apps.admin_forms import (
    AdminModelForm,
    model_admin_fields,
    model_admin_list_display,
)
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
    fields = model_admin_fields(Provider)
    readonly_fields = ("updated_at", "created_at")
    list_display = model_admin_list_display(
        Provider,
        exclude=("auth_token",),
    )
    search_fields = ["name"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    form = ProfileAdminForm
    fields = model_admin_fields(Profile)
    readonly_fields = ("updated_at", "created_at")
    list_display = model_admin_list_display(
        Profile,
        exclude=("response_format",),
    )
    list_select_related = ["provider"]
    search_fields = ["name", "provider__name"]
    list_filter = ["provider"]
