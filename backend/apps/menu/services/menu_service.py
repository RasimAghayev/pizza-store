from datetime import time

from django.utils import timezone

# calls apps.branches.services.branch_service.BranchService.{get_by_id,
# organization_id_for_restaurant}() -- see backend/apps/branches/README.md. menu never
# imports apps.branches.models/repositories directly (ADR 0004); MenuItem.branch is a lazy
# string FK for the same reason.
from apps.branches.services.branch_service import BranchService
from apps.menu.domain.availability import is_available_at
from apps.menu.models import MenuCategory, MenuItem
from apps.menu.repositories.menu_category_repository import MenuCategoryRepository
from apps.menu.repositories.menu_item_repository import MenuItemRepository

# calls apps.products.services.product_service.ProductService.get_by_id() -- see
# backend/apps/products/README.md. menu never imports apps.products.models/repositories
# directly (ADR 0004); MenuItem.product is a lazy string FK for the same reason.
from apps.products.services.product_service import ProductService


class MenuCategoryNotFoundError(Exception):
    pass


class MenuItemNotFoundError(Exception):
    pass


class BranchNotFoundError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


class CrossOrganizationMenuItemError(Exception):
    """Raised when a MenuItem's product or category belongs to a different organization
    than its branch -- a real data-integrity check, not merely an authorization one: the
    TwoStepPermission check on create only verifies the *branch* is in the requester's own
    scope, so without this a user could still link their own branch to someone else's
    product/category (not a privilege escalation, but a nonsensical cross-tenant row)."""

    pass


class DuplicateMenuItemError(Exception):
    pass


class MenuService:
    def __init__(
        self,
        category_repository: MenuCategoryRepository | None = None,
        item_repository: MenuItemRepository | None = None,
        branch_service: BranchService | None = None,
        product_service: ProductService | None = None,
    ) -> None:
        self._categories = category_repository or MenuCategoryRepository()
        self._items = item_repository or MenuItemRepository()
        self._branch_service = branch_service or BranchService()
        self._product_service = product_service or ProductService()

    def create_category(
        self, *, organization_id: int, name: str, display_order: int = 0
    ) -> MenuCategory:
        return self._categories.create(
            organization_id=organization_id, name=name, display_order=display_order
        )

    def get_category(self, category_id: int) -> MenuCategory | None:
        return self._categories.get_by_id(category_id)

    def list_categories_for_organization(self, organization_id: int) -> list[MenuCategory]:
        return self._categories.all_for_organization(organization_id)

    def update_category(self, category_id: int, **fields: object) -> MenuCategory:
        category = self._categories.get_by_id(category_id)
        if category is None:
            raise MenuCategoryNotFoundError(category_id)
        return self._categories.update(category, **fields)

    def delete_category(self, category_id: int) -> None:
        category = self._categories.get_by_id(category_id)
        if category is None:
            raise MenuCategoryNotFoundError(category_id)
        self._categories.delete(category)

    def organization_id_for_branch(self, branch_id: int) -> int | None:
        """`TwoStepPermission`'s scope hook for MenuItem needs the owning organization's id,
        which neither MenuItem nor Branch stores directly -- re-derived through
        `BranchService` (the sanctioned cross-module read, see this class's docstring).
        Takes `branch_id` directly (not a `MenuItem` instance) so the same lookup serves an
        existing MenuItem (`menu_item.branch_id`) and a not-yet-saved create payload alike."""
        branch = self._branch_service.get_by_id(branch_id)
        if branch is None:
            return None
        return self._branch_service.organization_id_for_restaurant(branch.restaurant_id)

    def create_item(
        self,
        *,
        branch_id: int,
        product_id: int,
        category_id: int,
        is_available: bool = True,
        available_from: time | None = None,
        available_until: time | None = None,
        display_order: int = 0,
    ) -> MenuItem:
        if self._branch_service.get_by_id(branch_id) is None:
            raise BranchNotFoundError(branch_id)
        organization_id = self.organization_id_for_branch(branch_id)

        product = self._product_service.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if product.organization_id != organization_id:
            raise CrossOrganizationMenuItemError(
                f"product {product_id} does not belong to branch {branch_id}'s organization"
            )

        category = self._categories.get_by_id(category_id)
        if category is None:
            raise MenuCategoryNotFoundError(category_id)
        if category.organization_id != organization_id:
            raise CrossOrganizationMenuItemError(
                f"category {category_id} does not belong to branch {branch_id}'s organization"
            )

        if self._items.exists_for_branch_and_product(branch_id, product_id):
            raise DuplicateMenuItemError(
                f"branch {branch_id} already has a menu item for product {product_id}"
            )

        return self._items.create(
            branch_id=branch_id,
            product_id=product_id,
            category_id=category_id,
            is_available=is_available,
            available_from=available_from,
            available_until=available_until,
            display_order=display_order,
        )

    def get_item(self, menu_item_id: int) -> MenuItem | None:
        return self._items.get_by_id(menu_item_id)

    def items_for_branch(self, branch_id: int) -> list[MenuItem]:
        """Unfiltered -- staff's own item list, so they can see/toggle an item that is
        currently unavailable or outside its window (Issue #182's Test Requirement)."""
        return self._items.all_for_branch(branch_id)

    def update_item(
        self, menu_item_id: int, *, category_id: int | None = None, **fields: object
    ) -> MenuItem:
        menu_item = self._items.get_by_id(menu_item_id)
        if menu_item is None:
            raise MenuItemNotFoundError(menu_item_id)

        if category_id is not None:
            category = self._categories.get_by_id(category_id)
            if category is None:
                raise MenuCategoryNotFoundError(category_id)
            organization_id = self.organization_id_for_branch(menu_item.branch_id)
            if category.organization_id != organization_id:
                raise CrossOrganizationMenuItemError(
                    f"category {category_id} does not belong to this menu item's organization"
                )
            fields["category_id"] = category_id

        return self._items.update(menu_item, **fields)

    def delete_item(self, menu_item_id: int) -> None:
        menu_item = self._items.get_by_id(menu_item_id)
        if menu_item is None:
            raise MenuItemNotFoundError(menu_item_id)
        self._items.delete(menu_item)

    def set_availability(self, menu_item_id: int, is_available: bool) -> MenuItem:
        return self.update_item(menu_item_id, is_available=is_available)

    def menu_for_branch(self, branch_id: int, *, at: time | None = None) -> list[MenuItem]:
        """The public, customer-facing listing (Issue #182's Implementation Prompt) -- only
        items currently `is_available=True` and, if a window is set, within
        `[available_from, available_until)` right now."""
        moment = at if at is not None else timezone.localtime().time()
        return [
            item
            for item in self._items.all_for_branch(branch_id)
            if is_available_at(
                is_available=item.is_available,
                available_from=item.available_from,
                available_until=item.available_until,
                at=moment,
            )
        ]
