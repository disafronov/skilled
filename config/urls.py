from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

from apps.bots import views as bots_views

urlpatterns = [
    path(
        "",
        RedirectView.as_view(
            url=reverse_lazy("admin:index"),
            permanent=False,
        ),
    ),
    path("admin/", admin.site.urls),
    path("health/", include("apps.health.urls")),
    path("webhook/<str:token>/", bots_views.webhook, name="webhook"),
]
