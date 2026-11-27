from django.db import models


class OptionChoice(models.Model):
    """One selectable value within an `OptionGroup` (e.g. "Large" under a size group) --
    `price_delta` is added to the product's base price when a customer selects it (see
    domain/pricing.py)."""

    option_group = models.ForeignKey(
        "products.OptionGroup", on_delete=models.CASCADE, related_name="choices"
    )
    name = models.CharField(max_length=255)
    price_delta = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        app_label = "products"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name
