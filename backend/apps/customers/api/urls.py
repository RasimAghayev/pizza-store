from django.urls import path

from apps.customers.api.views import CustomerRegistrationView

urlpatterns = [
    path("register/", CustomerRegistrationView.as_view(), name="customer-register"),
]
