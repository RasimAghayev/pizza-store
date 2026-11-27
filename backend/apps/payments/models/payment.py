from django.db import models

from apps.payments.domain.payment_method import PaymentMethod
from apps.payments.domain.payment_status import PaymentStatus

_GATEWAY_CHOICES = [(method.value, method.value) for method in PaymentMethod]
_STATUS_CHOICES = [(status.value, status.value) for status in PaymentStatus]


class Payment(models.Model):
    """One capture attempt against an Issue #197 `Order` (Issue #198). `order_id` is a plain
    field, not a cross-app FK (ADR 0004 -- same pattern as `Order.customer_id`): a Payment
    always belongs to exactly one real Order row, but ownership/cascade is enforced at the
    service layer (`services/payment_service.py::PaymentService`), not the DB layer.
    `provider_reference` is an opaque string handed back by the gateway (e.g. a mock
    authorization/capture id) -- never card data (Security Requirements: no PAN/CVV/expiry
    field exists anywhere in this module). `amount`/`currency` are always `Decimal`/a fixed
    ISO 4217 code, never `float` (CLAUDE.md)."""

    order_id = models.PositiveBigIntegerField(db_index=True)
    gateway = models.CharField(max_length=20, choices=_GATEWAY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=_STATUS_CHOICES)
    provider_reference = models.CharField(max_length=255, blank=True, default="")
    idempotency_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payments"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Payment(id={self.pk}, order_id={self.order_id}, status={self.status})"
