from django.db import models


class OptionGroupKind(models.TextChoices):
    SIZE = "size", "Size"
    DOUGH = "dough", "Dough"
    CRUST = "crust", "Crust"
    CHEESE = "cheese", "Cheese"
    SAUCE = "sauce", "Sauce"


class OptionGroup(models.Model):
    """Generic option-group covering size/dough/crust/cheese/sauce uniformly (Issue #181's
    Implementation Prompt) rather than five near-duplicate models -- each shares the same
    one-choice-with-a-price-delta shape. `is_required`/`allows_multiple` are set per
    instance so size/dough/crust/cheese (single-choice, required) and sauce (possibly
    optional/multi) can share this one model without a special case per kind."""

    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="option_groups"
    )
    kind = models.CharField(max_length=16, choices=OptionGroupKind.choices)
    is_required = models.BooleanField(default=True)
    allows_multiple = models.BooleanField(default=False)

    class Meta:
        app_label = "products"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product_id}:{self.kind}"
