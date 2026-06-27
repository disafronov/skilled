from django.contrib import admin

from apps.admin_forms import AdminModelForm
from apps.library.models import Skill, Wrapper


class SkillAdminForm(AdminModelForm):
    class Meta:
        model = Skill
        fields = "__all__"


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    form = SkillAdminForm
    fields = ("name", "content", "updated_at", "created_at")
    readonly_fields = ("updated_at", "created_at")
    list_display = ("name", "updated_at")
    search_fields = ["name"]


class WrapperAdminForm(AdminModelForm):
    class Meta:
        model = Wrapper
        fields = "__all__"


@admin.register(Wrapper)
class WrapperAdmin(admin.ModelAdmin):
    form = WrapperAdminForm
    fields = ("name", "skill", "content", "updated_at", "created_at")
    readonly_fields = ("updated_at", "created_at")
    list_display = ("name", "skill", "updated_at")
    list_select_related = ["skill"]
    search_fields = ["name"]
