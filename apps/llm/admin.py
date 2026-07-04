from django.contrib import admin

from apps.llm.models import Worker
from engine.common.admin_forms import AdminModelForm
from engine.common.admin_mixins import CHANGES_FIELDSET


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
