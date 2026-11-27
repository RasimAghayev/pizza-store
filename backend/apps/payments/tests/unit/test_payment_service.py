import pytest

from apps.orders.domain.state_machine import OrderStatus
from apps.orders.services.order_service import OrderNotFoundError, OrderService
from apps.orders.tests.factories import OrderFactory
from apps.payments.domain.gateway_registry import UnknownPaymentMethodError
from apps.payments.domain.mock_online_gateway import DECLINE_TOKEN
from apps.payments.domain.payment_method import PaymentMethod
from apps.payments.models.payment_outbox_event import PaymentOutboxEvent
from apps.payments.services.payment_service import OrderNotPendingPaymentError, PaymentService


def _pending_order():
    order = OrderFactory(status=OrderStatus.PENDING_PAYMENT.value)
    return order, order.customer_id


@pytest.mark.django_db
def test_capture_with_cash_on_delivery_confirms_the_order_and_creates_a_captured_payment():
    order, customer_id = _pending_order()

    payment = PaymentService().capture_for_order(
        order_id=order.pk,
        customer_id=customer_id,
        payment_method=PaymentMethod.CASH_ON_DELIVERY,
        payment_method_token=None,
        idempotency_key="key-1",
    )

    assert payment.status == "captured"
    assert payment.amount == order.total_amount
    confirmed_order = OrderService().get_owned(customer_id=customer_id, order_id=order.pk)
    assert confirmed_order.status == OrderStatus.CONFIRMED.value


@pytest.mark.django_db
def test_capture_with_mock_online_and_a_valid_token_confirms_the_order():
    order, customer_id = _pending_order()

    payment = PaymentService().capture_for_order(
        order_id=order.pk,
        customer_id=customer_id,
        payment_method=PaymentMethod.MOCK_ONLINE,
        payment_method_token="tok_visa",
        idempotency_key="key-2",
    )

    assert payment.status == "captured"
    confirmed_order = OrderService().get_owned(customer_id=customer_id, order_id=order.pk)
    assert confirmed_order.status == OrderStatus.CONFIRMED.value


@pytest.mark.django_db
def test_capture_with_mock_online_and_the_decline_token_fails_the_order():
    order, customer_id = _pending_order()

    payment = PaymentService().capture_for_order(
        order_id=order.pk,
        customer_id=customer_id,
        payment_method=PaymentMethod.MOCK_ONLINE,
        payment_method_token=DECLINE_TOKEN,
        idempotency_key="key-3",
    )

    assert payment.status == "failed"
    failed_order = OrderService().get_owned(customer_id=customer_id, order_id=order.pk)
    assert failed_order.status == OrderStatus.PAYMENT_FAILED.value


@pytest.mark.django_db
def test_capture_raises_when_the_order_is_not_pending_payment():
    order, customer_id = _pending_order()
    PaymentService().capture_for_order(
        order_id=order.pk,
        customer_id=customer_id,
        payment_method=PaymentMethod.CASH_ON_DELIVERY,
        payment_method_token=None,
        idempotency_key="key-4",
    )

    with pytest.raises(OrderNotPendingPaymentError):
        PaymentService().capture_for_order(
            order_id=order.pk,
            customer_id=customer_id,
            payment_method=PaymentMethod.CASH_ON_DELIVERY,
            payment_method_token=None,
            idempotency_key="key-5",
        )


@pytest.mark.django_db
def test_capture_raises_unknown_payment_method():
    order, customer_id = _pending_order()

    with pytest.raises(UnknownPaymentMethodError):
        PaymentService().capture_for_order(
            order_id=order.pk,
            customer_id=customer_id,
            payment_method="some_unregistered_method",
            payment_method_token=None,
            idempotency_key="key-6",
        )


@pytest.mark.django_db
def test_capture_raises_order_not_found_for_another_customers_order():
    order, _customer_id = _pending_order()
    other_customer_id = OrderFactory().customer_id

    with pytest.raises(OrderNotFoundError):
        PaymentService().capture_for_order(
            order_id=order.pk,
            customer_id=other_customer_id,
            payment_method=PaymentMethod.CASH_ON_DELIVERY,
            payment_method_token=None,
            idempotency_key="key-7",
        )


@pytest.mark.django_db
def test_capture_publishes_a_payment_completed_outbox_event_on_success():
    order, customer_id = _pending_order()

    payment = PaymentService().capture_for_order(
        order_id=order.pk,
        customer_id=customer_id,
        payment_method=PaymentMethod.CASH_ON_DELIVERY,
        payment_method_token=None,
        idempotency_key="key-8",
    )

    event = PaymentOutboxEvent.objects.get(aggregate_id=str(payment.pk))
    assert event.event_type == "payment.completed"
    assert event.payload["payment_id"] == payment.pk


@pytest.mark.django_db
def test_capture_publishes_a_payment_failed_outbox_event_on_failure():
    order, customer_id = _pending_order()

    payment = PaymentService().capture_for_order(
        order_id=order.pk,
        customer_id=customer_id,
        payment_method=PaymentMethod.MOCK_ONLINE,
        payment_method_token=DECLINE_TOKEN,
        idempotency_key="key-9",
    )

    event = PaymentOutboxEvent.objects.get(aggregate_id=str(payment.pk))
    assert event.event_type == "payment.failed"
    assert event.payload["reason"] == "card_declined"
