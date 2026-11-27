from decimal import Decimal
from typing import cast

import pytest

from apps.branches.tests.factories import BranchFactory
from apps.customers.models import Customer
from apps.customers.tests.factories import CustomerFactory
from apps.orders.domain.state_machine import OrderStatus
from apps.orders.repositories.order_repository import OrderRepository
from apps.orders.tests.factories import OrderFactory, OrderItemFactory


@pytest.mark.django_db
def test_create_order_persists_every_field():
    order = OrderRepository().create_order(
        customer_id=cast(Customer, CustomerFactory()).pk,
        branch_id=BranchFactory().pk,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=Decimal("10.00"),
        delivery_fee=Decimal("2.50"),
        discount_amount=Decimal("0.00"),
        total_amount=Decimal("12.50"),
        delivery_street_and_unit="1 Pizza Ave",
        delivery_city="Springfield",
        delivery_postal_code="12345",
        delivery_latitude=None,
        delivery_longitude=None,
        idempotency_key="repo-key-1",
    )

    assert order.status == OrderStatus.PENDING_PAYMENT.value
    assert order.total_amount == Decimal("12.50")


@pytest.mark.django_db
def test_create_items_bulk_creates_every_line():
    order = OrderFactory()

    items = OrderRepository().create_items(
        order.pk,
        [
            {
                "product_id": 1,
                "name": "Margherita",
                "selection": {},
                "unit_price": Decimal("10.00"),
                "quantity": 2,
                "line_total": Decimal("20.00"),
            },
            {
                "product_id": 2,
                "name": "Pepperoni",
                "selection": {},
                "unit_price": Decimal("12.00"),
                "quantity": 1,
                "line_total": Decimal("12.00"),
            },
        ],
    )

    assert len(items) == 2
    assert {item.order_id for item in items} == {order.pk}


@pytest.mark.django_db
def test_create_audit_allows_a_null_from_status_for_the_creation_row():
    order = OrderFactory()

    audit = OrderRepository().create_audit(
        order_id=order.pk,
        from_status=None,
        to_status=OrderStatus.PENDING_PAYMENT,
        reason=None,
    )

    assert audit.from_status is None
    assert audit.to_status == OrderStatus.PENDING_PAYMENT.value


@pytest.mark.django_db
def test_create_audit_records_a_real_transition():
    order = OrderFactory()

    audit = OrderRepository().create_audit(
        order_id=order.pk,
        from_status=OrderStatus.PENDING_PAYMENT,
        to_status=OrderStatus.CONFIRMED,
        reason="payment captured",
    )

    assert audit.from_status == OrderStatus.PENDING_PAYMENT.value
    assert audit.to_status == OrderStatus.CONFIRMED.value
    assert audit.reason == "payment captured"


@pytest.mark.django_db
def test_get_by_id_prefetches_items():
    order = OrderFactory()
    OrderItemFactory(order=order)

    found = OrderRepository().get_by_id(order.pk)

    assert found is not None
    assert len(found.items.all()) == 1


@pytest.mark.django_db
def test_get_for_customer_returns_none_for_a_different_customer():
    order = OrderFactory()
    other_customer_id = cast(Customer, CustomerFactory()).pk

    assert OrderRepository().get_for_customer(order.pk, other_customer_id) is None
    assert OrderRepository().get_for_customer(order.pk, order.customer_id) == order


@pytest.mark.django_db
def test_list_for_customer_only_returns_that_customers_orders():
    order = OrderFactory()
    OrderFactory()  # a different customer's order

    found = OrderRepository().list_for_customer(order.customer_id)

    assert [o.pk for o in found] == [order.pk]


@pytest.mark.django_db
def test_update_status_persists_the_new_value():
    order = OrderFactory(status=OrderStatus.PENDING_PAYMENT.value)

    updated = OrderRepository().update_status(order, OrderStatus.CONFIRMED)

    order.refresh_from_db()
    assert updated.status == OrderStatus.CONFIRMED.value
    assert order.status == OrderStatus.CONFIRMED.value
