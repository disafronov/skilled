from django.contrib import admin

from apps.admin_forms import (
    AdminModelForm,
    model_admin_fields,
    model_admin_list_display,
)
from apps.library.models import Skill, Wrapper


class SkillAdminForm(AdminModelForm):
    class Meta:
        model = Skill
        fields = "__all__"


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    form = SkillAdminForm
    fields = model_admin_fields(Skill)
    readonly_fields = ("updated_at", "created_at")
    list_display = model_admin_list_display(Skill, exclude=("content",))
    search_fields = ["name"]


class WrapperAdminForm(AdminModelForm):
    class Meta:
        model = Wrapper
        fields = "__all__"


@admin.register(Wrapper)
class WrapperAdmin(admin.ModelAdmin):
    form = WrapperAdminForm
    fields = model_admin_fields(Wrapper)
    readonly_fields = ("updated_at", "created_at")
    list_display = model_admin_list_display(Wrapper, exclude=("content",))
    search_fields = ["name"]
