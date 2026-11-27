from decimal import Decimal
from typing import cast

import pytest

from apps.branches.tests.factories import BranchFactory
from apps.cart.domain.branch_policy import DifferentBranchCartError
from apps.cart.services.cart_service import (
    BranchNotFoundError,
    CartItemNotFoundError,
    CartService,
    CustomerNotFoundError,
    InvalidCartItemSelectionError,
    ProductNotOrderableError,
)
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory
from apps.menu.tests.factories import MenuCategoryFactory, MenuItemFactory
from apps.products.services.pricing_service import PricingService
from apps.products.tests.factories import ProductFactory
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory


def _orderable_branch_and_product(**product_kwargs):
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    product = ProductFactory(organization_id=organization.pk, **product_kwargs)
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=product, category=category)
    return branch, product


def _customer_id() -> int:
    return cast(Customer, CustomerFactory()).pk


@pytest.mark.django_db
def test_add_item_persists_a_real_pricing_service_quote_as_the_snapshot():
    branch, product = _orderable_branch_and_product(base_price=Decimal("10.00"))
    customer_id = _customer_id()

    item = CartService().add_item(
        customer_id=customer_id, branch_id=branch.pk, product_id=product.pk
    )

    assert item.unit_price_snapshot == Decimal("10.00")


@pytest.mark.django_db
def test_add_item_raises_when_the_branch_does_not_exist():
    customer_id = _customer_id()

    with pytest.raises(BranchNotFoundError):
        CartService().add_item(customer_id=customer_id, branch_id=999_999, product_id=1)


@pytest.mark.django_db
def test_add_item_raises_when_the_customer_does_not_exist():
    branch, product = _orderable_branch_and_product()

    with pytest.raises(CustomerNotFoundError):
        CartService().add_item(customer_id=999_999, branch_id=branch.pk, product_id=product.pk)


@pytest.mark.django_db
def test_add_item_raises_when_the_product_has_no_menu_item_on_this_branch():
    branch = BranchFactory()
    product = ProductFactory()
    customer_id = _customer_id()

    with pytest.raises(ProductNotOrderableError):
        CartService().add_item(customer_id=customer_id, branch_id=branch.pk, product_id=product.pk)


@pytest.mark.django_db
def test_add_item_raises_when_the_menu_item_is_marked_unavailable():
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    product = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=product, category=category, is_available=False)
    customer_id = _customer_id()

    with pytest.raises(ProductNotOrderableError):
        CartService().add_item(customer_id=customer_id, branch_id=branch.pk, product_id=product.pk)


@pytest.mark.django_db
def test_add_item_raises_when_neither_product_id_nor_half_and_half_is_given():
    branch, _ = _orderable_branch_and_product()
    customer_id = _customer_id()

    with pytest.raises(InvalidCartItemSelectionError):
        CartService().add_item(customer_id=customer_id, branch_id=branch.pk)


@pytest.mark.django_db
def test_add_item_raises_when_both_product_id_and_half_and_half_are_given():
    branch, product = _orderable_branch_and_product()
    customer_id = _customer_id()

    with pytest.raises(InvalidCartItemSelectionError):
        CartService().add_item(
            customer_id=customer_id,
            branch_id=branch.pk,
            product_id=product.pk,
            half_and_half={
                "first": {"product_id": product.pk},
                "second": {"product_id": product.pk},
            },
        )


@pytest.mark.django_db
def test_add_item_for_a_different_branch_is_rejected_while_the_current_cart_has_items():
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    first_branch = BranchFactory(restaurant=restaurant)
    second_branch = BranchFactory(restaurant=restaurant)
    product_a = ProductFactory(organization_id=organization.pk)
    product_b = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=first_branch, product=product_a, category=category)
    MenuItemFactory(branch=second_branch, product=product_b, category=category)
    customer_id = _customer_id()

    CartService().add_item(
        customer_id=customer_id, branch_id=first_branch.pk, product_id=product_a.pk
    )

    with pytest.raises(DifferentBranchCartError):
        CartService().add_item(
            customer_id=customer_id, branch_id=second_branch.pk, product_id=product_b.pk
        )


@pytest.mark.django_db
def test_clear_then_switching_branch_succeeds():
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    first_branch = BranchFactory(restaurant=restaurant)
    second_branch = BranchFactory(restaurant=restaurant)
    product_a = ProductFactory(organization_id=organization.pk)
    product_b = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=first_branch, product=product_a, category=category)
    MenuItemFactory(branch=second_branch, product=product_b, category=category)
    customer_id = _customer_id()
    CartService().add_item(
        customer_id=customer_id, branch_id=first_branch.pk, product_id=product_a.pk
    )

    CartService().clear(customer_id)
    item = CartService().add_item(
        customer_id=customer_id, branch_id=second_branch.pk, product_id=product_b.pk
    )

    assert item.cart.branch_id == second_branch.pk


@pytest.mark.django_db
def test_update_item_quantity_changes_the_stored_quantity():
    branch, product = _orderable_branch_and_product()
    customer_id = _customer_id()
    item = CartService().add_item(
        customer_id=customer_id, branch_id=branch.pk, product_id=product.pk
    )

    updated = CartService().update_item_quantity(
        customer_id=customer_id, item_id=item.pk, quantity=4
    )

    assert updated.quantity == 4


@pytest.mark.django_db
def test_update_item_quantity_for_another_customers_item_raises_not_found():
    branch, product = _orderable_branch_and_product()
    owner_id = _customer_id()
    other_id = _customer_id()
    item = CartService().add_item(customer_id=owner_id, branch_id=branch.pk, product_id=product.pk)

    with pytest.raises(CartItemNotFoundError):
        CartService().update_item_quantity(customer_id=other_id, item_id=item.pk, quantity=2)


@pytest.mark.django_db
def test_remove_item_deletes_it_from_the_cart():
    branch, product = _orderable_branch_and_product()
    customer_id = _customer_id()
    item = CartService().add_item(
        customer_id=customer_id, branch_id=branch.pk, product_id=product.pk
    )

    CartService().remove_item(customer_id=customer_id, item_id=item.pk)

    priced = CartService().get_priced_active_cart(customer_id)
    assert priced.items == []


@pytest.mark.django_db
def test_get_priced_active_cart_returns_the_empty_shape_for_a_customer_with_no_cart():
    customer_id = _customer_id()

    priced = CartService().get_priced_active_cart(customer_id)

    assert priced.id is None
    assert priced.branch_id is None
    assert priced.items == []
    assert priced.total == Decimal("0.00")


@pytest.mark.django_db
def test_total_matches_a_fresh_quote_call_for_a_half_and_half_item_with_quantity():
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    first = ProductFactory(organization_id=organization.pk, base_price=Decimal("10.00"))
    second = ProductFactory(organization_id=organization.pk, base_price=Decimal("10.01"))
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=first, category=category)
    MenuItemFactory(branch=branch, product=second, category=category)
    customer_id = _customer_id()
    half_and_half = {"first": {"product_id": first.pk}, "second": {"product_id": second.pk}}

    item = CartService().add_item(
        customer_id=customer_id,
        branch_id=branch.pk,
        half_and_half=half_and_half,
        quantity=3,
    )

    expected_total = PricingService().quote(
        half_and_half=(half_and_half["first"], half_and_half["second"]), quantity=3
    )
    priced = CartService().get_priced_active_cart(customer_id)
    assert len(priced.items) == 1
    assert priced.items[0].line_total == expected_total
    assert priced.total == expected_total
    assert item.half_and_half == half_and_half


@pytest.mark.django_db
def test_price_drifts_from_the_stale_snapshot_after_the_products_base_price_changes():
    branch, product = _orderable_branch_and_product(base_price=Decimal("10.00"))
    customer_id = _customer_id()
    item = CartService().add_item(
        customer_id=customer_id, branch_id=branch.pk, product_id=product.pk
    )
    assert item.unit_price_snapshot == Decimal("10.00")

    product.base_price = Decimal("12.50")
    product.save(update_fields=["base_price"])

    priced = CartService().get_priced_active_cart(customer_id)
    assert priced.items[0].unit_price == Decimal("12.50")
    assert priced.items[0].line_total == Decimal("12.50")
