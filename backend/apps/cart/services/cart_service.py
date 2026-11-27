from dataclasses import dataclass
from decimal import Decimal

from apps.branches.services.branch_service import BranchService
from apps.cart.domain.branch_policy import DifferentBranchCartError, can_add_to_branch
from apps.cart.models import Cart, CartItem
from apps.cart.repositories.cart_repository import CartRepository

# calls apps.customers.services.profile_service.ProfileService.get_by_id() -- see
# backend/apps/customers/README.md. cart never imports apps.customers.models/repositories
# directly (ADR 0004); Cart.customer_id is a plain field for the same reason.
from apps.customers.services.profile_service import ProfileService

# calls apps.menu.services.menu_service.MenuService.is_orderable_now() -- see
# backend/apps/menu/README.md. cart never imports apps.menu.models/repositories directly
# (ADR 0004).
from apps.menu.services.menu_service import MenuService

# calls apps.products.services.pricing_service.PricingService.quote() -- see
# backend/apps/products/README.md. cart never imports apps.products.models/repositories
# directly (ADR 0004); this is the exact live-repricing Issue #181 named as Phase 11's job.
from apps.products.services.pricing_service import PricingService

__all__ = [
    "CartService",
    "CustomerNotFoundError",
    "BranchNotFoundError",
    "ProductNotOrderableError",
    "CartNotFoundError",
    "CartItemNotFoundError",
    "InvalidCartItemSelectionError",
    "DifferentBranchCartError",
    "PricedCart",
    "PricedCartItem",
]


class CustomerNotFoundError(Exception):
    pass


class BranchNotFoundError(Exception):
    pass


class ProductNotOrderableError(Exception):
    pass


class CartNotFoundError(Exception):
    pass


class CartItemNotFoundError(Exception):
    """Raised for an item id that doesn't exist, or exists but isn't in the requesting
    customer's own active cart -- the view maps both cases to the same 404, never a 403
    (same pattern as `apps.customers.services.address_service.AddressNotFoundError`)."""


class InvalidCartItemSelectionError(Exception):
    pass


@dataclass(frozen=True)
class PricedCartItem:
    id: int
    product_id: int | None
    option_choice_ids: list[int]
    topping_ids: list[int]
    half_and_half: dict | None
    quantity: int
    note: str
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class PricedCart:
    id: int | None
    branch_id: int | None
    items: list[PricedCartItem]
    total: Decimal


_EMPTY_CART = PricedCart(id=None, branch_id=None, items=[], total=Decimal("0.00"))


class CartService:
    def __init__(
        self,
        repository: CartRepository | None = None,
        branch_service: BranchService | None = None,
        menu_service: MenuService | None = None,
        pricing_service: PricingService | None = None,
        profile_service: ProfileService | None = None,
    ) -> None:
        self._carts = repository or CartRepository()
        self._branch_service = branch_service or BranchService()
        self._menu_service = menu_service or MenuService()
        self._pricing_service = pricing_service or PricingService()
        self._profile_service = profile_service or ProfileService()

    def get_or_create_cart(self, *, customer_id: int, branch_id: int) -> Cart:
        if self._branch_service.get_by_id(branch_id) is None:
            raise BranchNotFoundError(branch_id)

        active = self._carts.active_cart_for_customer(customer_id)
        if not can_add_to_branch(
            existing_cart_branch_id=active.branch_id if active is not None else None,
            existing_cart_has_items=active is not None,
            requested_branch_id=branch_id,
        ):
            raise DifferentBranchCartError(
                f"customer {customer_id} already has an open cart for a different branch; "
                "clear it before adding an item for another branch."
            )

        cart = self._carts.get_cart_for_customer_and_branch(
            customer_id=customer_id, branch_id=branch_id
        )
        if cart is not None:
            return cart

        if self._profile_service.get_by_id(customer_id) is None:
            raise CustomerNotFoundError(customer_id)
        return self._carts.create_cart(customer_id=customer_id, branch_id=branch_id)

    def get_active_cart(self, customer_id: int) -> Cart | None:
        return self._carts.active_cart_for_customer(customer_id)

    def get_priced_active_cart(self, customer_id: int) -> PricedCart:
        """`GET /api/v1/cart/`'s one call -- the customer's cart is a singleton resource
        that always "exists" from the client's point of view, so a customer who has never
        added anything gets a 200 empty-cart shape here, never a 404."""
        cart = self._carts.active_cart_for_customer(customer_id)
        if cart is None:
            return _EMPTY_CART
        return self.price_cart(cart)

    def add_item(
        self,
        *,
        customer_id: int,
        branch_id: int,
        product_id: int | None = None,
        option_choice_ids: list[int] | None = None,
        topping_ids: list[int] | None = None,
        half_and_half: dict | None = None,
        quantity: int = 1,
        note: str = "",
    ) -> CartItem:
        if (product_id is None) == (half_and_half is None):
            raise InvalidCartItemSelectionError(
                "Exactly one of product_id or half_and_half must be provided."
            )

        cart = self.get_or_create_cart(customer_id=customer_id, branch_id=branch_id)

        if product_id is not None:
            product_ids = [product_id]
        elif half_and_half is not None:
            product_ids = [
                half_and_half["first"]["product_id"],
                half_and_half["second"]["product_id"],
            ]
        else:
            raise InvalidCartItemSelectionError(
                "Exactly one of product_id or half_and_half must be provided."
            )
        for pid in product_ids:
            if not self._menu_service.is_orderable_now(branch_id=branch_id, product_id=pid):
                raise ProductNotOrderableError(
                    f"product {pid} is not orderable at branch {branch_id} right now."
                )

        unit_price_snapshot = self._quote_unit(
            product_id=product_id,
            option_choice_ids=option_choice_ids,
            topping_ids=topping_ids,
            half_and_half=half_and_half,
        )

        return self._carts.create_item(
            cart_id=cart.pk,
            product_id=product_id,
            option_choice_ids=option_choice_ids or [],
            topping_ids=topping_ids or [],
            half_and_half=half_and_half,
            quantity=quantity,
            note=note,
            unit_price_snapshot=unit_price_snapshot,
        )

    def update_item_quantity(self, *, customer_id: int, item_id: int, quantity: int) -> CartItem:
        item = self._get_owned_item(customer_id=customer_id, item_id=item_id)
        return self._carts.update_item_quantity(item, quantity)

    def remove_item(self, *, customer_id: int, item_id: int) -> None:
        item = self._get_owned_item(customer_id=customer_id, item_id=item_id)
        self._carts.delete_item(item)

    def clear(self, customer_id: int) -> None:
        cart = self._carts.active_cart_for_customer(customer_id)
        if cart is not None:
            self._carts.clear(cart.pk)

    def price_cart(self, cart: Cart) -> PricedCart:
        items = self._carts.items_for_cart(cart.pk)
        priced_items = [self._price_item(item) for item in items]
        total = sum((priced.line_total for priced in priced_items), Decimal("0.00"))
        return PricedCart(id=cart.pk, branch_id=cart.branch_id, items=priced_items, total=total)

    def current_total(self, cart_id: int) -> Decimal:
        cart = self._carts.get_cart_by_id(cart_id)
        if cart is None:
            raise CartNotFoundError(cart_id)
        return self.price_cart(cart).total

    def _price_item(self, item: CartItem) -> PricedCartItem:
        """`unit_price` and `line_total` are each an independent, direct
        `PricingService.quote()` call (quantity=1 and quantity=`item.quantity`
        respectively) -- never `unit_price * item.quantity` computed by hand. Issue #196's
        own Test Requirement demands the total "matches a fresh `PricingService.quote()`
        call for every line"; `calculate_price()` rounds the real quantity-multiplied total
        in one step (see `apps/products/domain/pricing.py`), which is not always identical
        to rounding a quantity=1 unit price first and multiplying that *rounded* value by
        quantity second -- re-deriving `line_total` from `unit_price` would silently drift
        from what a fresh quote call returns on a half-and-half build whenever the
        unrounded average lands on a third decimal place."""
        unit_price = self._quote_unit(
            product_id=item.product_id,
            option_choice_ids=item.option_choice_ids,
            topping_ids=item.topping_ids,
            half_and_half=item.half_and_half,
        )
        line_total = self._quote_total(
            product_id=item.product_id,
            option_choice_ids=item.option_choice_ids,
            topping_ids=item.topping_ids,
            half_and_half=item.half_and_half,
            quantity=item.quantity,
        )
        return PricedCartItem(
            id=item.pk,
            product_id=item.product_id,
            option_choice_ids=item.option_choice_ids,
            topping_ids=item.topping_ids,
            half_and_half=item.half_and_half,
            quantity=item.quantity,
            note=item.note,
            unit_price=unit_price,
            line_total=line_total,
        )

    def _quote_unit(
        self,
        *,
        product_id: int | None,
        option_choice_ids: list[int] | None,
        topping_ids: list[int] | None,
        half_and_half: dict | None,
    ) -> Decimal:
        """A true per-unit price (`quantity=1`) -- what `CartItem.unit_price_snapshot`
        stores at add-time, and what a live read shows as `unit_price` (recomputed, never
        read back from the snapshot)."""
        return self._quote_total(
            product_id=product_id,
            option_choice_ids=option_choice_ids,
            topping_ids=topping_ids,
            half_and_half=half_and_half,
            quantity=1,
        )

    def _quote_total(
        self,
        *,
        product_id: int | None,
        option_choice_ids: list[int] | None,
        topping_ids: list[int] | None,
        half_and_half: dict | None,
        quantity: int,
    ) -> Decimal:
        if half_and_half is not None:
            return self._pricing_service.quote(
                half_and_half=(half_and_half["first"], half_and_half["second"]),
                quantity=quantity,
            )
        return self._pricing_service.quote(
            product_id=product_id,
            option_choice_ids=option_choice_ids or [],
            topping_ids=topping_ids or [],
            quantity=quantity,
        )

    def _get_owned_item(self, *, customer_id: int, item_id: int) -> CartItem:
        """Ownership-only, 404-not-403 on mismatch (same pattern as
        `apps.customers.services.address_service.AddressService.get_owned`): a client never
        learns whether an id belongs to someone else's cart or doesn't exist at all."""
        cart = self._carts.active_cart_for_customer(customer_id)
        item = (
            self._carts.get_item_for_cart(item_id=item_id, cart_id=cart.pk)
            if cart is not None
            else None
        )
        if item is None:
            raise CartItemNotFoundError(item_id)
        return item
