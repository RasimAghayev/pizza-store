from django.db import models


class Branch(models.Model):
    """A physical, orderable location (master prompt §11; ADR 0006 Context). `restaurant`
    uses a lazy string FK (`models.ForeignKey("restaurants.Restaurant", ...)`) -- it resolves
    through Django's app registry at runtime with no `import apps.restaurants...` statement
    in this module's code, satisfying `import-linter`'s contract (ADR 0004) while keeping a
    real DB-level foreign key. `minimum_order_amount`/`delivery_fee` are `Decimal`, never
    `float` (CLAUDE.md)."""

    restaurant = models.ForeignKey(
        "restaurants.Restaurant", on_delete=models.CASCADE, related_name="branches"
    )
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    phone = models.CharField(max_length=32)
    delivery_radius_km = models.DecimalField(max_digits=5, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    average_prep_time_minutes = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "branches"

    def __str__(self) -> str:
        return self.name
