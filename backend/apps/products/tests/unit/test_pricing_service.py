from decimal import Decimal

import pytest

from apps.products.services.pricing_service import InvalidPriceQuoteError, PricingService
from apps.products.tests.factories import (
    OptionChoiceFactory,
    OptionGroupFactory,
    ProductFactory,
    ToppingFactory,
)


@pytest.mark.django_db
def test_quote_raises_when_the_product_does_not_exist():
    with pytest.raises(InvalidPriceQuoteError):
        PricingService().quote(product_id=999_999)


@pytest.mark.django_db
def test_quote_raises_when_an_option_choice_does_not_belong_to_the_product():
    product = ProductFactory()
    other_products_choice = OptionChoiceFactory()

    with pytest.raises(InvalidPriceQuoteError):
        PricingService().quote(product_id=product.pk, option_choice_ids=[other_products_choice.pk])


@pytest.mark.django_db
def test_quote_raises_when_a_topping_is_not_attached_to_the_product():
    product = ProductFactory()
    topping = ToppingFactory()

    with pytest.raises(InvalidPriceQuoteError):
        PricingService().quote(product_id=product.pk, topping_ids=[topping.pk])


@pytest.mark.django_db
def test_quote_matches_calculate_price_for_a_simple_build():
    product = ProductFactory(base_price=Decimal("10.00"))
    group = OptionGroupFactory(product=product, kind="size")
    choice = OptionChoiceFactory(option_group=group, price_delta=Decimal("2.00"))

    price = PricingService().quote(product_id=product.pk, option_choice_ids=[choice.pk], quantity=3)

    assert price == Decimal("36.00")


@pytest.mark.django_db
def test_quote_for_half_and_half_averages_the_two_products():
    first = ProductFactory(base_price=Decimal("10.00"))
    second = ProductFactory(base_price=Decimal("14.00"))

    price = PricingService().quote(
        half_and_half=({"product_id": first.pk}, {"product_id": second.pk})
    )

    assert price == Decimal("12.00")
