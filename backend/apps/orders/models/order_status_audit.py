from django.db import models

from apps.orders.domain.state_machine import OrderStatus
from apps.orders.models.order import Order

_STATUS_CHOICES = [(status.value, status.value) for status in OrderStatus]


class OrderStatusAudit(models.Model):
    """One row per status change on an `Order` (Issue #197), in Postgres -- not MongoDB, per
    ADR 0002 (`orders`/`order_items` and their direct audit trail live only in PostgreSQL; a
    richer free-form order *event history* for analytics is a separate, future MongoDB
    concern, not this one). `from_status` is nullable only for the one row
    `OrderService.checkout()` inserts directly at creation (there is no prior status to
    record -- creating an Order is not itself a state-machine *transition*); every later row
    is inserted by `OrderService.transition()`, the sole writer for every row after the
    first, always inside the same DB transaction as the status change itself."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_audits")
    from_status = models.CharField(max_length=20, choices=_STATUS_CHOICES, null=True, blank=True)
    to_status = models.CharField(max_length=20, choices=_STATUS_CHOICES)
    reason = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "orders"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return (
            f"OrderStatusAudit(order_id={self.order_id}, " f"{self.from_status}->{self.to_status})"
        )
