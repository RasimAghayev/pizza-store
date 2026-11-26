# called by Nginx/a future load balancer's health probe -- see backend/health/views.py
from django.urls import include, path

urlpatterns = [
    path("health/", include("health.urls")),
]
