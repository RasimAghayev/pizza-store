from django.db import models

from apps.orders.models.order import Order


class OrderItem(models.Model):
    """An immutable snapshot of one checked-out cart line (Issue #197) -- `product_id` is a
    plain, nullable integer with no FK at all (not even a lazy string one): a line must stay
    exactly as priced/named at checkout time even if the referenced `products.Product` row is
    later edited or deleted, so no live join is ever used to render an existing order.
    Nullable because a half-and-half line has no single product (see `selection` below).
    `order` is a real FK via a direct import since `Order` lives in this same module/app
    (same reasoning as `apps.customers.models.Address.customer`).

    `selection` preserves the exact choice shape `CartItem` stored (`option_choice_ids`/
    `topping_ids`/`half_and_half`), so a historical order can still show precisely what was
    ordered. `unit_price`/`line_total` are each the fresh `PricingService.quote()` result
    `OrderService.checkout()` computed at checkout time -- not derived from each other by
    hand-multiplication, same reasoning as Issue #196's `CartService._price_item`."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_id = models.PositiveBigIntegerField(null=True, blank=True)
    name = models.CharField(max_length=255)
    selection = models.JSONField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = "orders"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"OrderItem(id={self.pk}, order_id={self.order_id})"
