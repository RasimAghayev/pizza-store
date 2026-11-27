from django.urls import path

from apps.payments.api.views import PaymentCaptureView

urlpatterns = [
    path("", PaymentCaptureView.as_view(), name="payment-capture"),
]
