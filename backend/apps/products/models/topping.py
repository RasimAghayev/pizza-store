from django.db import models


class Topping(models.Model):
    """Shared, platform-wide catalog entry -- not product-specific. `ProductTopping` (see
    product_topping.py) attaches it to one or more products. `sku_reference` is the named,
    not-yet-built integration point for Phase 12's inventory module (Issue #181's Technical
    Context) -- deliberately unused by anything in this Task."""

    name = models.CharField(max_length=255)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sku_reference = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        app_label = "products"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
