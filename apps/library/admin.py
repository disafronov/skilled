from django.contrib import admin

from apps.library.models import Skill, Wrapper


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at", "updated_at"]
    search_fields = ["name"]


@admin.register(Wrapper)
class WrapperAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at", "updated_at"]
    search_fields = ["name"]
