class DifferentBranchCartError(Exception):
    """Raised when a customer tries to add an item for a branch other than the one their
    current non-empty cart belongs to -- see `can_add_to_branch`'s docstring for the
    Task's own choice of behavior here, documented in `README.md`."""


def can_add_to_branch(
    *, existing_cart_branch_id: int | None, existing_cart_has_items: bool, requested_branch_id: int
) -> bool:
    """Pure, Django-import-free (ADR 0004). Issue #196 leaves "what happens when a customer
    adds an item from a different branch than their currently-open cart" unspecified by
    design and requires this Task's own single, consistently-applied choice (same pattern as
    Issue #181's half-and-half pricing decision): **reject**, not silently clear-and-switch.

    A customer's cart is scoped to exactly one branch at a time once it holds an item --
    `CartService.add_item` calls this before writing anything, and raises
    `DifferentBranchCartError` when it returns `False` so the client can show its own
    "switching branches clears your cart" confirmation and then explicitly call
    `DELETE /api/v1/cart/` (`CartService.clear`) before retrying, rather than this module
    silently discarding the customer's existing selection on their behalf. An empty existing
    cart for a different branch (no items ever added, or already cleared) imposes no
    restriction -- only a cart that actually holds something blocks a branch switch."""

    if existing_cart_branch_id is None or not existing_cart_has_items:
        return True
    return existing_cart_branch_id == requested_branch_id
