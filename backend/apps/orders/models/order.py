from django.db import models

from apps.orders.domain.state_machine import OrderStatus
from shared.encryption.fields import EncryptedCharField

_STATUS_CHOICES = [(status.value, status.value) for status in OrderStatus]


class Order(models.Model):
    """A checked-out Cart (Issue #197) -- never created before `OrderService.checkout()`,
    always starts in `OrderStatus.PENDING_PAYMENT`. `customer_id` is a plain field, not a
    cross-app FK to `customers.Customer` (ADR 0004 forbids this app importing
    `apps.customers.models`), same pattern as Issue #196's `Cart.customer_id`. `branch` is a
    real DB-level FK via a lazy string (`models.ForeignKey("branches.Branch", ...)`) -- an
    Order always belongs to exactly one real branch row and a genuine cascade relationship is
    appropriate here, same reasoning as `apps.menu.MenuItem.branch`.

    `delivery_*` fields are a snapshot of the customer's chosen `apps.customers.models.Address`
    taken at checkout time, not a live FK -- an address later edited or deleted must never
    retroactively change an already-placed order. `delivery_street_and_unit` is the only
    encrypted one, mirroring `Address.street_and_unit` (ADR 0006).

    `discount_amount` is always `0.00` in this Task -- the discount/campaign engine is Phase
    13's job; the column exists now so Phase 13 doesn't need a schema migration to add it.
    All money fields are `Decimal`, never `float` (CLAUDE.md)."""

    customer_id = models.PositiveBigIntegerField()
    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=_STATUS_CHOICES)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_street_and_unit = EncryptedCharField()
    delivery_city = models.CharField(max_length=100)
    delivery_postal_code = models.CharField(max_length=20, blank=True, default="")
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    idempotency_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "orders"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order(id={self.pk}, customer_id={self.customer_id}, status={self.status})"
