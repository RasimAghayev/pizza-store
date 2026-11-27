from django.db import models


class Product(models.Model):
    """One pizza "line" (e.g. "Margherita"), not a specific customer-built combination --
    see domain/pricing.py for how a customer's selected options turn into a final price.
    `organization_id` is a plain field, not a cross-app FK to `restaurants.Organization`
    (ADR 0004 forbids this app importing `apps.restaurants.models`), same pattern as
    `identity.RoleAssignment.organization_id` -- existence is validated once at create time
    by `ProductService` through `restaurants`' own sanctioned `OrganizationService` entry
    point, not enforced by a DB constraint. Product is org-scoped, never branch-scoped --
    per-branch menu availability is Issue #182's concern, not this one's."""

    organization_id = models.PositiveBigIntegerField()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "products"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
