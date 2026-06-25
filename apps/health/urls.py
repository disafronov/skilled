from django.http import HttpRequest, HttpResponse
from django.urls import path, reverse

from .health import liveness, readiness

app_name = "health"


def health_index(request: HttpRequest) -> HttpResponse:
    liveness_url = reverse("health:liveness")
    readiness_url = reverse("health:readiness")
    return HttpResponse(
        f'<a href="{liveness_url}">liveness</a><br>'
        f'<a href="{readiness_url}">readiness</a>'
    )


urlpatterns = [
    path("", health_index, name="health-index"),
    path("liveness/", liveness, name="liveness"),
    path("readiness/", readiness, name="readiness"),
]
