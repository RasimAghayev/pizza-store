from decimal import Decimal

import pytest

from apps.orders.tests.factories import OrderFactory
from apps.payments.domain.payment_status import PaymentStatus
from apps.payments.repositories.payment_repository import PaymentRepository
from apps.payments.tests.factories import PaymentFactory


@pytest.mark.django_db
def test_create_payment_persists_every_field():
    order = OrderFactory()

    payment = PaymentRepository().create_payment(
        order_id=order.pk,
        gateway="cash_on_delivery",
        amount=Decimal("12.50"),
        currency="USD",
        status=PaymentStatus.CAPTURED,
        provider_reference="cash_on_delivery",
        idempotency_key="repo-key-1",
    )

    assert payment.order_id == order.pk
    assert payment.status == PaymentStatus.CAPTURED.value
    assert payment.amount == Decimal("12.50")


@pytest.mark.django_db
def test_get_by_id_returns_none_for_an_unknown_id():
    assert PaymentRepository().get_by_id(999_999) is None


@pytest.mark.django_db
def test_get_by_id_returns_the_matching_payment():
    payment = PaymentFactory()

    found = PaymentRepository().get_by_id(payment.pk)

    assert found == payment


@pytest.mark.django_db
def test_list_for_order_only_returns_that_orders_payments():
    order = OrderFactory()
    matching = PaymentFactory(order_id=order.pk)
    PaymentFactory()  # a different order's payment

    found = PaymentRepository().list_for_order(order.pk)

    assert [p.pk for p in found] == [matching.pk]
