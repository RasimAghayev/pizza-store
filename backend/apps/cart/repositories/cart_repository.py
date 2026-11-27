from decimal import Decimal

from apps.cart.models import Cart, CartItem


class CartRepository:
    """Only file in this module allowed to issue an ORM query for `Cart`/`CartItem`, per
    ADR 0004."""

    def create_cart(self, *, customer_id: int, branch_id: int) -> Cart:
        return Cart.objects.create(customer_id=customer_id, branch_id=branch_id)

    def get_cart_for_customer_and_branch(self, *, customer_id: int, branch_id: int) -> Cart | None:
        return Cart.objects.filter(customer_id=customer_id, branch_id=branch_id).first()

    def get_cart_by_id(self, cart_id: int) -> Cart | None:
        return Cart.objects.filter(pk=cart_id).first()

    def active_cart_for_customer(self, customer_id: int) -> Cart | None:
        """The one cart, if any, that currently has items -- the customer-facing notion of
        "my cart" (Issue #196's single-active-cart-per-customer rule, see
        `apps/cart/domain/branch_policy.py`). A customer may have other, empty `Cart` rows
        left over from a past branch switch; those are harmless and never surfaced here."""
        return (
            Cart.objects.filter(customer_id=customer_id, items__isnull=False)
            .distinct()
            .order_by("-updated_at")
            .first()
        )

    def create_item(
        self,
        *,
        cart_id: int,
        product_id: int | None,
        option_choice_ids: list[int],
        topping_ids: list[int],
        half_and_half: dict | None,
        quantity: int,
        note: str,
        unit_price_snapshot: Decimal,
    ) -> CartItem:
        return CartItem.objects.create(
            cart_id=cart_id,
            product_id=product_id,
            option_choice_ids=option_choice_ids,
            topping_ids=topping_ids,
            half_and_half=half_and_half,
            quantity=quantity,
            note=note,
            unit_price_snapshot=unit_price_snapshot,
        )

    def get_item_for_cart(self, *, item_id: int, cart_id: int) -> CartItem | None:
        return CartItem.objects.filter(pk=item_id, cart_id=cart_id).first()

    def items_for_cart(self, cart_id: int) -> list[CartItem]:
        return list(CartItem.objects.filter(cart_id=cart_id))

    def update_item_quantity(self, item: CartItem, quantity: int) -> CartItem:
        item.quantity = quantity
        item.save(update_fields=["quantity"])
        return item

    def delete_item(self, item: CartItem) -> None:
        item.delete()

    def clear(self, cart_id: int) -> None:
        CartItem.objects.filter(cart_id=cart_id).delete()
