import json
from typing import cast

import pytest
from django.test import Client

from apps.customers.models.customer import Customer
from apps.customers.tests.factories import CustomerFactory
from apps.identity.models import User
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.orders.domain.state_machine import OrderStatus
from apps.orders.models import Order
from apps.orders.tests.factories import OrderFactory
from apps.payments.domain.mock_online_gateway import DECLINE_TOKEN
from apps.payments.models.payment import Payment

PAYMENTS_URL = "/api/v1/payments/"


def _authenticated(client) -> Customer:
    user = cast(User, UserFactory())
    customer = cast(Customer, CustomerFactory(user_id=user.pk))
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return customer


def _post_json(client, payload, *, idempotency_key=None):
    headers = {}
    if idempotency_key is not None:
        headers["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
    return client.post(
        PAYMENTS_URL, data=json.dumps(payload), content_type="application/json", **headers
    )


def _pending_order_for(customer_id):
    return OrderFactory(customer_id=customer_id, status=OrderStatus.PENDING_PAYMENT.value)


@pytest.mark.django_db
def test_capture_without_an_idempotency_key_is_rejected(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)

    response = _post_json(client, {"order_id": order.pk, "payment_method": "cash_on_delivery"})

    assert response.status_code == 400
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_capture_requires_a_payment_method_token_for_mock_online(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)

    response = _post_json(
        client,
        {"order_id": order.pk, "payment_method": "mock_online"},
        idempotency_key="missing-token-key",
    )

    assert response.status_code == 400
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_capture_rejects_a_payment_method_token_for_cash_on_delivery(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)

    response = _post_json(
        client,
        {
            "order_id": order.pk,
            "payment_method": "cash_on_delivery",
            "payment_method_token": "tok_visa",
        },
        idempotency_key="unexpected-token-key",
    )

    assert response.status_code == 400
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_capture_with_cash_on_delivery_succeeds_and_confirms_the_order(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)

    response = _post_json(
        client,
        {"order_id": order.pk, "payment_method": "cash_on_delivery"},
        idempotency_key="cod-key",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "captured"
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED.value


@pytest.mark.django_db
def test_capture_with_mock_online_and_a_valid_token_succeeds(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)

    response = _post_json(
        client,
        {
            "order_id": order.pk,
            "payment_method": "mock_online",
            "payment_method_token": "tok_visa",
        },
        idempotency_key="mock-success-key",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "captured"
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED.value


@pytest.mark.django_db
def test_capture_with_the_decline_token_returns_a_failed_payment_and_fails_the_order(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)

    response = _post_json(
        client,
        {
            "order_id": order.pk,
            "payment_method": "mock_online",
            "payment_method_token": DECLINE_TOKEN,
        },
        idempotency_key="mock-decline-key",
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    order.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_FAILED.value


@pytest.mark.django_db
def test_duplicate_capture_with_the_same_idempotency_key_captures_exactly_once(client):
    """The literal Issue #198 acceptance criterion."""
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)
    payload = {"order_id": order.pk, "payment_method": "cash_on_delivery"}

    first = _post_json(client, payload, idempotency_key="duplicate-capture-key")
    second = _post_json(client, payload, idempotency_key="duplicate-capture-key")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert Payment.objects.filter(order_id=order.pk).count() == 1


@pytest.mark.django_db
def test_capture_on_an_order_not_pending_payment_is_rejected(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)
    payload = {"order_id": order.pk, "payment_method": "cash_on_delivery"}
    _post_json(client, payload, idempotency_key="first-capture-key")

    response = _post_json(client, payload, idempotency_key="second-different-capture-key")

    assert response.status_code == 400
    assert Payment.objects.filter(order_id=order.pk).count() == 1


@pytest.mark.django_db
def test_capture_on_another_customers_order_returns_404(client):
    owner = _authenticated(Client())
    order = _pending_order_for(owner.pk)
    _authenticated(client)

    response = _post_json(
        client,
        {"order_id": order.pk, "payment_method": "cash_on_delivery"},
        idempotency_key="wrong-owner-key",
    )

    assert response.status_code == 404
    assert Payment.objects.count() == 0


@pytest.mark.django_db
def test_capture_on_an_unknown_order_returns_404(client):
    _authenticated(client)

    response = _post_json(
        client,
        {"order_id": 999_999, "payment_method": "cash_on_delivery"},
        idempotency_key="unknown-order-key",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_capture_money_fields_are_decimal_strings_never_floats(client):
    customer = _authenticated(client)
    order = _pending_order_for(customer.pk)

    response = _post_json(
        client,
        {"order_id": order.pk, "payment_method": "cash_on_delivery"},
        idempotency_key="decimal-key",
    )

    assert response.status_code == 201
    assert isinstance(response.json()["amount"], str)
    assert response.json()["amount"] == str(Order.objects.get(pk=order.pk).total_amount)
