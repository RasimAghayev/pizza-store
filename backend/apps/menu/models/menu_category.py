from django.db import models


class MenuCategory(models.Model):
    """Belongs to the organization's catalog (e.g. "Pizzas", "Sides"), not to a single
    branch (Issue #182's Implementation Prompt) -- same plain-field, no-cross-app-FK
    `organization_id` pattern as `apps.products.Product` (Issue #181) and
    `apps.identity.RoleAssignment`, for the same reason: no direct Python import of
    `apps.restaurants.models` from this app (ADR 0004)."""

    organization_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=255)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "menu"
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name
