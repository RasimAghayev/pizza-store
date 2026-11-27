from decimal import Decimal
from typing import cast

import pytest

from apps.branches.tests.factories import BranchFactory

# calls apps.cart.services.cart_service.CartService -- see backend/apps/cart/README.md.
# Builds a real, orderable cart the same way a customer's own requests would, so checkout
# exercises CartService.price_cart() against genuine CartItem rows (ADR 0004: orders never
# imports apps.cart.models directly, so even this test only ever goes through the service).
from apps.cart.services.cart_service import CartService
from apps.customers.models import Customer
from apps.customers.tests.factories import AddressFactory, CustomerFactory
from apps.menu.tests.factories import MenuCategoryFactory, MenuItemFactory
from apps.orders.domain.state_machine import IllegalOrderTransitionError, OrderStatus
from apps.orders.models.order_outbox_event import OrderOutboxEvent
from apps.orders.services.order_service import (
    AddressNotFoundError,
    BelowMinimumOrderAmountError,
    CartNotFoundError,
    OrderNotFoundError,
    OrderService,
)
from apps.products.services.pricing_service import PricingService
from apps.products.tests.factories import ProductFactory
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory


def _customer_id() -> int:
    return cast(Customer, CustomerFactory()).pk


def _orderable_branch_and_product(**branch_kwargs):
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant, **branch_kwargs)
    product = ProductFactory(organization_id=organization.pk, base_price=Decimal("10.00"))
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=product, category=category)
    return branch, product


def _checkout_ready_cart(customer_id: int, *, quantity: int = 1, **branch_kwargs):
    branch, product = _orderable_branch_and_product(**branch_kwargs)
    CartService().add_item(
        customer_id=customer_id, branch_id=branch.pk, product_id=product.pk, quantity=quantity
    )
    cart = CartService().get_active_cart(customer_id)
    address = AddressFactory(customer_id=customer_id)
    return cart, branch, product, address


@pytest.mark.django_db
def test_checkout_computes_the_total_from_fresh_quotes_plus_delivery_fee():
    customer_id = _customer_id()
    cart, branch, product, address = _checkout_ready_cart(customer_id, quantity=2)

    order = OrderService().checkout(
        customer_id=customer_id,
        cart_id=cart.pk,
        address_id=address.pk,
        idempotency_key="key-1",
    )

    expected_subtotal = PricingService().quote(product_id=product.pk, quantity=2)
    assert order.subtotal == expected_subtotal
    assert order.delivery_fee == branch.delivery_fee
    assert order.total_amount == expected_subtotal + branch.delivery_fee
    assert order.status == OrderStatus.PENDING_PAYMENT
    assert order.idempotency_key == "key-1"
    assert order.delivery_city == address.city


@pytest.mark.django_db
def test_checkout_clears_the_cart():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)

    OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-2"
    )

    assert CartService().get_active_cart(customer_id) is None


@pytest.mark.django_db
def test_checkout_raises_cart_not_found_for_a_customer_with_no_active_cart():
    customer_id = _customer_id()
    address = AddressFactory(customer_id=customer_id)

    with pytest.raises(CartNotFoundError):
        OrderService().checkout(
            customer_id=customer_id,
            cart_id=999_999,
            address_id=address.pk,
            idempotency_key="key-3",
        )


@pytest.mark.django_db
def test_checkout_raises_cart_not_found_when_cart_id_does_not_match_the_active_cart():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)
    other_customer_id = _customer_id()
    other_cart, _, _, _ = _checkout_ready_cart(other_customer_id)

    with pytest.raises(CartNotFoundError):
        OrderService().checkout(
            customer_id=customer_id,
            cart_id=other_cart.pk,
            address_id=address.pk,
            idempotency_key="key-4",
        )


@pytest.mark.django_db
def test_checkout_raises_address_not_found_for_an_address_owned_by_someone_else():
    customer_id = _customer_id()
    cart, _branch, _product, _address = _checkout_ready_cart(customer_id)
    someone_elses_address = AddressFactory()

    with pytest.raises(AddressNotFoundError):
        OrderService().checkout(
            customer_id=customer_id,
            cart_id=cart.pk,
            address_id=someone_elses_address.pk,
            idempotency_key="key-5",
        )


@pytest.mark.django_db
def test_checkout_raises_below_minimum_order_amount():
    customer_id = _customer_id()
    cart, branch, _product, address = _checkout_ready_cart(
        customer_id, minimum_order_amount=Decimal("50.00")
    )

    with pytest.raises(BelowMinimumOrderAmountError):
        OrderService().checkout(
            customer_id=customer_id,
            cart_id=cart.pk,
            address_id=address.pk,
            idempotency_key="key-6",
        )


@pytest.mark.django_db
def test_checkout_half_and_half_item_snapshot_combines_both_product_names():
    customer_id = _customer_id()
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    first = ProductFactory(organization_id=organization.pk, name="Margherita")
    second = ProductFactory(organization_id=organization.pk, name="Pepperoni")
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=first, category=category)
    MenuItemFactory(branch=branch, product=second, category=category)
    half_and_half = {"first": {"product_id": first.pk}, "second": {"product_id": second.pk}}
    CartService().add_item(
        customer_id=customer_id, branch_id=branch.pk, half_and_half=half_and_half
    )
    cart = CartService().get_active_cart(customer_id)
    address = AddressFactory(customer_id=customer_id)

    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-7"
    )

    item = order.items.get()
    assert item.name == "Margherita / Pepperoni (Half & Half)"
    assert item.selection == {"half_and_half": half_and_half}


@pytest.mark.django_db
def test_checkout_inserts_the_initial_audit_row_with_a_null_from_status():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)

    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-8"
    )

    audit = order.status_audits.get()
    assert audit.from_status is None
    assert audit.to_status == OrderStatus.PENDING_PAYMENT


@pytest.mark.django_db
def test_checkout_publishes_an_order_created_outbox_event():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)

    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-9"
    )

    event = OrderOutboxEvent.objects.get(aggregate_id=str(order.pk))
    assert event.event_type == "order.created"
    assert event.payload["order_id"] == order.pk


@pytest.mark.django_db
def test_transition_updates_status_and_inserts_an_audit_row():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)
    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-10"
    )

    updated = OrderService().transition(
        order_id=order.pk, to_status=OrderStatus.CONFIRMED, reason="payment captured"
    )

    assert updated.status == OrderStatus.CONFIRMED
    audits = list(updated.status_audits.order_by("created_at"))
    assert len(audits) == 2
    assert audits[-1].from_status == OrderStatus.PENDING_PAYMENT
    assert audits[-1].to_status == OrderStatus.CONFIRMED
    assert audits[-1].reason == "payment captured"


@pytest.mark.django_db
def test_transition_raises_on_an_illegal_edge():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)
    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-11"
    )

    with pytest.raises(IllegalOrderTransitionError):
        OrderService().transition(order_id=order.pk, to_status=OrderStatus.DELIVERED)


@pytest.mark.django_db
def test_transition_raises_order_not_found_for_an_unknown_id():
    with pytest.raises(OrderNotFoundError):
        OrderService().transition(order_id=999_999, to_status=OrderStatus.CONFIRMED)


@pytest.mark.django_db
def test_transition_to_confirmed_publishes_an_order_confirmed_event():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)
    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-12"
    )

    OrderService().transition(order_id=order.pk, to_status=OrderStatus.CONFIRMED)

    confirmed_events = OrderOutboxEvent.objects.filter(
        aggregate_id=str(order.pk), event_type="order.confirmed"
    )
    assert confirmed_events.count() == 1


@pytest.mark.django_db
def test_transition_to_a_non_confirmed_status_does_not_publish_an_order_confirmed_event():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)
    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-13"
    )

    OrderService().transition(order_id=order.pk, to_status=OrderStatus.CANCELLED)

    assert not OrderOutboxEvent.objects.filter(
        aggregate_id=str(order.pk), event_type="order.confirmed"
    ).exists()


@pytest.mark.django_db
def test_get_owned_raises_not_found_for_another_customers_order():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)
    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-14"
    )
    other_customer_id = _customer_id()

    with pytest.raises(OrderNotFoundError):
        OrderService().get_owned(customer_id=other_customer_id, order_id=order.pk)


@pytest.mark.django_db
def test_list_for_customer_only_returns_that_customers_own_orders():
    customer_id = _customer_id()
    cart, _branch, _product, address = _checkout_ready_cart(customer_id)
    order = OrderService().checkout(
        customer_id=customer_id, cart_id=cart.pk, address_id=address.pk, idempotency_key="key-15"
    )
    other_customer_id = _customer_id()
    other_cart, _, _, other_address = _checkout_ready_cart(other_customer_id)
    OrderService().checkout(
        customer_id=other_customer_id,
        cart_id=other_cart.pk,
        address_id=other_address.pk,
        idempotency_key="key-16",
    )

    orders = OrderService().list_for_customer(customer_id)

    assert [o.pk for o in orders] == [order.pk]
