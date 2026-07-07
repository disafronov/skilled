import tomllib
from pathlib import Path

from django.contrib import admin
from django.urls import path, reverse_lazy
from django.views.generic import RedirectView

from apps.ops.health import liveness, readiness
from engine.telegram import views as bots_views

_pyproject = tomllib.loads(
    (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text("utf-8")
)
admin.site.index_title = f"skilled {_pyproject['project']['version']}"

urlpatterns = [
    path(
        "",
        RedirectView.as_view(
            url=reverse_lazy("admin:index"),
            permanent=False,
        ),
    ),
    path("admin/", admin.site.urls),
    path("health/liveness/", liveness, name="liveness"),
    path("health/readiness/", readiness, name="readiness"),
    path("webhook/", bots_views.webhook, name="webhook"),
]
