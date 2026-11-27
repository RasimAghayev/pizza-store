from django.db import models


class Cart(models.Model):
    """One row per `(customer_id, branch_id)` pair a customer has ever added an item to
    (Issue #196). `customer_id` is a plain field, not a cross-app FK to `customers.Customer`
    (ADR 0004 forbids this app importing `apps.customers.models`), same pattern as
    `apps.products.models.Product.organization_id` -- existence is validated once at create
    time by `CartService` through `customers`' own sanctioned `ProfileService` entry point,
    not enforced by a DB constraint. `branch` is a lazy string FK
    (`models.ForeignKey("branches.Branch", ...)`), same pattern as `apps.menu.MenuItem.branch`
    -- a cart is genuinely owned/composed by its branch (cascade-delete makes sense here,
    unlike the looser organization-scoping relationship `organization_id` represents), and a
    real DB-level FK costs nothing extra since `branches` is a dependency `cart` is allowed to
    have a real relationship with.

    A customer may only have one cart with items in it at a time across all branches -- see
    `domain/branch_policy.py` and `README.md` for the branch-switch rule this Task's own
    choice settles (the Issue leaves it unspecified by design)."""

    customer_id = models.PositiveBigIntegerField()
    branch = models.ForeignKey("branches.Branch", on_delete=models.CASCADE, related_name="carts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cart"
        constraints = [
            models.UniqueConstraint(
                fields=["customer_id", "branch"], name="unique_cart_customer_branch"
            )
        ]

    def __str__(self) -> str:
        return f"Cart(customer_id={self.customer_id}, branch_id={self.branch_id})"
