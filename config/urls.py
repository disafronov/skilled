from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

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
]
