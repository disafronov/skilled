from django.contrib import admin
from apps.inference.models import Provider, Profile


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ['name', 'api_type', 'base_url', 'created_at']
    search_fields = ['name']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'model', 'temperature', 'max_output_tokens', 'created_at']
    search_fields = ['name']
