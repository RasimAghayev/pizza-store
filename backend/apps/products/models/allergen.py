from django.db import models


class Allergen(models.Model):
    """M2M to both `Product` and `Topping` -- an allergen can come from either the base
    product or an added topping (Issue #181's Implementation Prompt)."""

    name = models.CharField(max_length=255, unique=True)
    products = models.ManyToManyField("products.Product", related_name="allergens", blank=True)
    toppings = models.ManyToManyField("products.Topping", related_name="allergens", blank=True)

    class Meta:
        app_label = "products"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
