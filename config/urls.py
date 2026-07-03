from django.contrib import admin
from django.urls import path, reverse_lazy
from django.views.generic import RedirectView

from config.health import liveness, readiness
from engine.telegram import views as bots_views

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
