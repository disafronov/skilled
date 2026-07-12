from django.contrib import admin
from django_telegram_q2.common.admin import CHANGES_FIELDSET, AdminModelForm

from apps.library.models import Skill, Wrapper


class SkillAdminForm(AdminModelForm):
    class Meta:
        model = Skill
        fields = "__all__"


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    form = SkillAdminForm
    fieldsets = (  # type: ignore[assignment]
        (
            None,
            {
                "fields": ("name", "content"),
            },
        ),
        CHANGES_FIELDSET,
    )
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
    fieldsets = (  # type: ignore[assignment]
        (
            None,
            {
                "fields": ("name", "skill", "content"),
            },
        ),
        CHANGES_FIELDSET,
    )
    readonly_fields = ("updated_at", "created_at")
    list_display = ("name", "skill", "updated_at")
    list_select_related = ["skill"]
    search_fields = ["name"]
