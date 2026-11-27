from django.db import models


class ProductTopping(models.Model):
    """Through-model distinguishing toppings that come standard on a product (removable at
    no charge) from add-on toppings (charged via `Topping.price_delta`) -- Issue #181's
    Implementation Prompt. `(product, topping)` is unique -- attaching an already-attached
    topping again updates its `is_default_included` flag instead (see
    repositories/product_topping_repository.py), mirroring `BusinessHours`' own
    `update_or_create` convention (Issue #180) rather than erroring on a duplicate."""

    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="product_toppings"
    )
    topping = models.ForeignKey(
        "products.Topping", on_delete=models.CASCADE, related_name="product_toppings"
    )
    is_default_included = models.BooleanField(default=False)

    class Meta:
        app_label = "products"
        constraints = [
            models.UniqueConstraint(fields=["product", "topping"], name="unique_product_topping")
        ]
