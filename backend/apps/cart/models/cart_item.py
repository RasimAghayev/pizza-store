from django.db import models


class CartItem(models.Model):
    """One customer-built pizza line inside a `Cart` (Issue #196). `cart` is a real FK since
    `Cart`/`CartItem` live in the same module/cluster, same reasoning as
    `apps.customers.Address.customer`. `product` is a lazy string FK to `products.Product`
    (same pattern as `apps.menu.MenuItem.product`) for a single-build item; **nullable**
    because a half-and-half item (see `half_and_half` below) has no single product -- exactly
    one of `product`/`half_and_half` is set, enforced by `CartService.add_item`, not a DB
    `CheckConstraint` (consistent with how `PricingService.quote()` already validates this
    same either/or in Python, see `apps/products/services/pricing_service.py`).

    `option_choice_ids`/`topping_ids` are plain-integer JSON lists, not M2M fields -- they
    describe a single build's selections for `product` only (ignored/empty for a
    half-and-half item). `half_and_half`, when set, is
    `{"first": {"product_id", "option_choice_ids", "topping_ids"},
    "second": {same shape}}` -- the exact shape `PricingService.quote(half_and_half=...)`
    expects once converted to its tuple-of-dicts form (see `services/cart_service.py`).

    `unit_price_snapshot` is the price `PricingService.quote()` returned at add-time, stored
    for audit/history only -- **never** the authoritative price shown to a customer. Every
    read re-quotes live through the same service so a later `base_price`/option-price change
    can never leave a stale price on screen (Issue #196 Architecture Requirements)."""

    cart = models.ForeignKey("cart.Cart", on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="+", null=True, blank=True
    )
    option_choice_ids = models.JSONField(default=list, blank=True)
    topping_ids = models.JSONField(default=list, blank=True)
    half_and_half = models.JSONField(null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=500, blank=True, default="")
    unit_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cart"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"CartItem(id={self.pk}, cart_id={self.cart_id})"
