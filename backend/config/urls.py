# called by Nginx/a future load balancer's health probe -- see backend/health/views.py
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# calls GET /api/v1/ping/ -- see backend/shared/api/views.py::PingView
from shared.api.views import PingView

urlpatterns = [
    path("health/", include("health.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    # Every module's api/urls.py will be mounted the same way, under
    # api/<version>/<module>/... -- see docs/api/conventions.md.
    path("api/<str:version>/ping/", PingView.as_view(), name="ping"),
]
