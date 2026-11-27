from django.urls import path

from apps.customers.api.views import (
    AddressDetailView,
    AddressListCreateView,
    CustomerRegistrationView,
    ProfileConsentView,
    ProfileView,
)

urlpatterns = [
    path("register/", CustomerRegistrationView.as_view(), name="customer-register"),
    path("me/profile/", ProfileView.as_view(), name="customer-profile"),
    path("me/profile/consent/", ProfileConsentView.as_view(), name="customer-profile-consent"),
    path("me/addresses/", AddressListCreateView.as_view(), name="customer-addresses"),
    path(
        "me/addresses/<int:pk>/",
        AddressDetailView.as_view(),
        name="customer-address-detail",
    ),
]
