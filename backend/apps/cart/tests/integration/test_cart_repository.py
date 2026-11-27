from decimal import Decimal
from typing import cast

import pytest
from django.db import IntegrityError

from apps.cart.models import Cart
from apps.cart.repositories.cart_repository import CartRepository
from apps.cart.tests.factories import CartFactory, CartItemFactory
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory


@pytest.mark.django_db
def test_create_cart_then_get_by_customer_and_branch_returns_it():
    cart = CartFactory()

    found = CartRepository().get_cart_for_customer_and_branch(
        customer_id=cart.customer_id, branch_id=cart.branch_id
    )

    assert found == cart


@pytest.mark.django_db
def test_unique_constraint_rejects_a_second_cart_for_the_same_customer_and_branch():
    cart = CartFactory()

    with pytest.raises(IntegrityError):
        Cart.objects.create(customer_id=cart.customer_id, branch_id=cart.branch_id)


@pytest.mark.django_db
def test_active_cart_for_customer_is_none_when_every_cart_is_empty():
    cart = CartFactory()

    assert CartRepository().active_cart_for_customer(cart.customer_id) is None


@pytest.mark.django_db
def test_active_cart_for_customer_returns_the_cart_that_has_items():
    cart = CartFactory()
    CartItemFactory(cart=cart)

    found = CartRepository().active_cart_for_customer(cart.customer_id)

    assert found == cart


@pytest.mark.django_db
def test_clear_removes_every_item_but_keeps_the_cart_row():
    cart = CartFactory()
    CartItemFactory(cart=cart)
    CartItemFactory(cart=cart)

    CartRepository().clear(cart.pk)

    assert CartRepository().items_for_cart(cart.pk) == []
    assert CartRepository().get_cart_by_id(cart.pk) is not None


@pytest.mark.django_db
def test_get_item_for_cart_returns_none_for_an_item_in_a_different_cart():
    item = CartItemFactory()
    other_customer_id = cast(Customer, CustomerFactory()).pk
    other_cart = CartFactory(customer_id=other_customer_id)

    assert CartRepository().get_item_for_cart(item_id=item.pk, cart_id=other_cart.pk) is None


@pytest.mark.django_db
def test_update_item_quantity_persists_the_new_value():
    item = CartItemFactory(quantity=1, unit_price_snapshot=Decimal("5.00"))

    CartRepository().update_item_quantity(item, 7)

    item.refresh_from_db()
    assert item.quantity == 7
