from django.contrib import admin

from apps.admin_forms import MaskedFieldsAdminForm
from apps.inference.models import Profile, Provider


class ProviderAdminForm(MaskedFieldsAdminForm):
    masked_fields = ("auth_token",)

    class Meta:
        model = Provider
        fields = "__all__"


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    form = ProviderAdminForm
    list_display = ["name", "api_type", "base_url", "created_at"]
    search_fields = ["name"]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "provider",
        "model",
        "temperature",
        "max_output_tokens",
        "created_at",
    ]
    list_select_related = ["provider"]
    search_fields = ["name", "provider__name"]
    list_filter = ["provider"]
