from django.db import models


class MenuItem(models.Model):
    """Links one `Branch` to one `Product` with its own per-branch availability (master
    prompt §11: "one branch's menu is not automatically dependent on another's") --
    `branch`/`product` are lazy string FKs (`models.ForeignKey("branches.Branch", ...)` /
    `models.ForeignKey("products.Product", ...)`), resolved through Django's app registry at
    runtime with no `import apps.branches...`/`import apps.products...` in this module's
    code, satisfying `import-linter`'s contract (ADR 0004) while keeping a real DB-level
    foreign key -- same pattern `apps.branches.Branch.restaurant` already established.
    `available_from`/`available_until` are nullable time-of-day fields: both null means
    "always available whenever the branch is open"; set means the half-open window
    `[available_from, available_until)`, time-of-day only -- a window that crosses midnight
    (`available_from > available_until`) is not supported, left out deliberately rather than
    assumed (see `domain/availability.py` and `README.md`)."""

    branch = models.ForeignKey(
        "branches.Branch", on_delete=models.CASCADE, related_name="menu_items"
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.CASCADE, related_name="menu_items"
    )
    category = models.ForeignKey(
        "menu.MenuCategory", on_delete=models.CASCADE, related_name="items"
    )
    is_available = models.BooleanField(default=True)
    available_from = models.TimeField(null=True, blank=True)
    available_until = models.TimeField(null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "menu"
        ordering = ["display_order"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "product"], name="unique_branch_product")
        ]

    def __str__(self) -> str:
        return f"MenuItem(branch={self.branch_id}, product={self.product_id})"
