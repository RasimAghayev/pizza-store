"""Pure pricing domain logic for a customer's selected pizza build -- no Django import
(ADR 0004), consumes/returns only plain dataclasses so it is independently unit-testable
and reusable from both `PricingService` (ORM-backed) and tests (hand-built fixtures).
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class ProductSelection:
    """One fully-specified half of a pizza build: a product's base price plus every
    option-choice delta and every non-default topping delta the customer picked for it.
    Default-included toppings contribute no delta -- they are already priced into
    `base_price`; only toppings added on top of (or removed from -- removal has no
    price effect, Issue #181 only prices additions) the default set carry a delta."""

    base_price: Decimal
    option_choice_deltas: tuple[Decimal, ...] = field(default_factory=tuple)
    non_default_topping_deltas: tuple[Decimal, ...] = field(default_factory=tuple)

    def unit_price(self) -> Decimal:
        return (
            self.base_price
            + sum(self.option_choice_deltas, Decimal("0"))
            + sum(self.non_default_topping_deltas, Decimal("0"))
        )


def calculate_price(
    selection: ProductSelection | None = None,
    *,
    half_and_half: tuple[ProductSelection, ProductSelection] | None = None,
    quantity: int = 1,
) -> Decimal:
    """Deterministic base price from selected options (Issue #181) -- no promotions/
    discounts, that is a separate future pricing/discounts module (ADR 0001).

    Half-and-half rule (the Issue leaves this unspecified and requires the Task's own
    choice to be documented, not assumed -- see `backend/apps/products/README.md`): each
    half is an independent, fully-specified `ProductSelection` (its own base price + its
    own option deltas + its own non-default topping deltas); the two halves' unit prices
    are AVERAGED, not summed, to get the combined pizza's unit price -- a half-and-half
    pizza costs the same as picking either half outright on average, not double.

    Quantity multiplies the per-unit price LAST, after per-unit summation/averaging is
    complete -- quantity never distributes across the option/topping deltas individually.

    The final result is explicitly rounded to 2 decimal places (ROUND_HALF_UP) rather than
    relying on implicit serializer-level rounding, since averaging two prices can produce
    a third decimal place (e.g. (10.00 + 10.01) / 2 = 10.005).
    """

    if half_and_half is not None:
        first, second = half_and_half
        unit_price = (first.unit_price() + second.unit_price()) / 2
    elif selection is not None:
        unit_price = selection.unit_price()
    else:
        raise ValueError("Either selection or half_and_half must be provided.")

    total = unit_price * quantity
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
