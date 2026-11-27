from decimal import Decimal

from apps.products.domain.pricing import ProductSelection, calculate_price
from apps.products.repositories.option_choice_repository import OptionChoiceRepository
from apps.products.repositories.product_repository import ProductRepository
from apps.products.repositories.product_topping_repository import ProductToppingRepository


class InvalidPriceQuoteError(Exception):
    pass


class PricingService:
    """Translates ORM rows into `domain.pricing.ProductSelection` dataclasses and calls the
    pure `calculate_price()` function -- this is what `POST /api/v1/products/<id>/price-quote/`
    (Issue #181's Implementation Prompt) calls, and what Phase 11's cart/checkout will call
    for the same deterministic price-from-selected-options calculation."""

    def __init__(
        self,
        product_repository: ProductRepository | None = None,
        option_choice_repository: OptionChoiceRepository | None = None,
        product_topping_repository: ProductToppingRepository | None = None,
    ) -> None:
        self._products = product_repository or ProductRepository()
        self._option_choices = option_choice_repository or OptionChoiceRepository()
        self._product_toppings = product_topping_repository or ProductToppingRepository()

    def quote(
        self,
        *,
        product_id: int | None = None,
        option_choice_ids: list[int] | None = None,
        topping_ids: list[int] | None = None,
        half_and_half: tuple[dict, dict] | None = None,
        quantity: int = 1,
    ) -> Decimal:
        if half_and_half is not None:
            first = self._build_selection(
                product_id=half_and_half[0]["product_id"],
                option_choice_ids=half_and_half[0].get("option_choice_ids") or [],
                topping_ids=half_and_half[0].get("topping_ids") or [],
            )
            second = self._build_selection(
                product_id=half_and_half[1]["product_id"],
                option_choice_ids=half_and_half[1].get("option_choice_ids") or [],
                topping_ids=half_and_half[1].get("topping_ids") or [],
            )
            return calculate_price(half_and_half=(first, second), quantity=quantity)

        if product_id is None:
            raise InvalidPriceQuoteError(
                "product_id is required when half_and_half is not provided."
            )
        selection = self._build_selection(
            product_id=product_id,
            option_choice_ids=option_choice_ids or [],
            topping_ids=topping_ids or [],
        )
        return calculate_price(selection, quantity=quantity)

    def _build_selection(
        self, *, product_id: int, option_choice_ids: list[int], topping_ids: list[int]
    ) -> ProductSelection:
        product = self._products.get_by_id(product_id)
        if product is None:
            raise InvalidPriceQuoteError(f"Product {product_id} does not exist.")

        option_choices = self._option_choices.filter_by_ids(option_choice_ids)
        if len(option_choices) != len(set(option_choice_ids)):
            raise InvalidPriceQuoteError("One or more option choices do not exist.")
        mismatched = [
            choice for choice in option_choices if choice.option_group.product_id != product_id
        ]
        if mismatched:
            raise InvalidPriceQuoteError("Selected option choices do not belong to this product.")

        default_topping_ids = {
            product_topping.topping_id
            for product_topping in self._product_toppings.all_for_product(product_id)
            if product_topping.is_default_included
        }
        non_default_topping_deltas = []
        for topping_id in topping_ids:
            product_topping = self._product_toppings.get(
                product_id=product_id, topping_id=topping_id
            )
            if product_topping is None:
                raise InvalidPriceQuoteError(
                    f"Topping {topping_id} is not attached to product {product_id}."
                )
            if topping_id not in default_topping_ids:
                non_default_topping_deltas.append(product_topping.topping.price_delta)

        return ProductSelection(
            base_price=product.base_price,
            option_choice_deltas=tuple(choice.price_delta for choice in option_choices),
            non_default_topping_deltas=tuple(non_default_topping_deltas),
        )
