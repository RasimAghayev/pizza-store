from django.urls import path

from apps.restaurants.api.views import (
    OrganizationDetailView,
    OrganizationListCreateView,
    RestaurantDetailView,
    RestaurantListCreateView,
)

urlpatterns = [
    path("organizations/", OrganizationListCreateView.as_view(), name="organization-list-create"),
    path("organizations/<int:pk>/", OrganizationDetailView.as_view(), name="organization-detail"),
    path("", RestaurantListCreateView.as_view(), name="restaurant-list-create"),
    path("<int:pk>/", RestaurantDetailView.as_view(), name="restaurant-detail"),
]
