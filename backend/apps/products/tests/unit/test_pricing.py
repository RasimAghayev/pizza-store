from decimal import Decimal

import pytest

from apps.products.domain.pricing import ProductSelection, calculate_price


def test_base_price_alone():
    selection = ProductSelection(base_price=Decimal("10.00"))

    assert calculate_price(selection) == Decimal("10.00")


def test_every_option_kind_delta_applied_once():
    selection = ProductSelection(
        base_price=Decimal("10.00"),
        option_choice_deltas=(
            Decimal("2.00"),  # size
            Decimal("1.00"),  # dough
            Decimal("1.50"),  # crust
            Decimal("0.75"),  # cheese
            Decimal("0.25"),  # sauce
        ),
    )

    assert calculate_price(selection) == Decimal("15.50")


def test_default_included_topping_has_no_price_effect():
    with_default_only = ProductSelection(base_price=Decimal("10.00"))

    assert calculate_price(with_default_only) == Decimal("10.00")


def test_non_default_topping_delta_is_added():
    selection = ProductSelection(
        base_price=Decimal("10.00"), non_default_topping_deltas=(Decimal("1.50"),)
    )

    assert calculate_price(selection) == Decimal("11.50")


def test_half_and_half_averages_the_two_halves_unit_prices():
    first = ProductSelection(base_price=Decimal("10.00"))
    second = ProductSelection(base_price=Decimal("14.00"))

    assert calculate_price(half_and_half=(first, second)) == Decimal("12.00")


def test_half_and_half_averaging_rounds_half_up_to_two_decimal_places():
    first = ProductSelection(base_price=Decimal("10.00"))
    second = ProductSelection(base_price=Decimal("10.01"))

    assert calculate_price(half_and_half=(first, second)) == Decimal("10.01")


def test_quantity_multiplies_after_per_unit_summation_not_before():
    selection = ProductSelection(
        base_price=Decimal("10.00"), non_default_topping_deltas=(Decimal("1.00"),)
    )

    # If quantity distributed across the deltas individually before summation, a naive
    # (and wrong) implementation might compute (10.00 * 2) + 1.00 = 21.00 instead of
    # (10.00 + 1.00) * 2 = 22.00 -- this asserts the correct order.
    assert calculate_price(selection, quantity=2) == Decimal("22.00")


def test_half_and_half_quantity_multiplies_after_averaging():
    first = ProductSelection(base_price=Decimal("10.00"))
    second = ProductSelection(base_price=Decimal("12.00"))

    assert calculate_price(half_and_half=(first, second), quantity=3) == Decimal("33.00")


def test_calculate_price_requires_either_selection_or_half_and_half():
    with pytest.raises(ValueError):
        calculate_price()
