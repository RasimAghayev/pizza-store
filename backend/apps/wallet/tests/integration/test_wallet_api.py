import json
from decimal import Decimal
from typing import cast

import pytest
from django.test import Client

from apps.customers.models.customer import Customer
from apps.customers.tests.factories import CustomerFactory
from apps.identity.models import User
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.orders.domain.state_machine import OrderStatus
from apps.orders.tests.factories import OrderFactory

WALLET_URL = "/api/v1/wallet/"
TOPUP_URL = "/api/v1/wallet/topup/"
PAYMENTS_URL = "/api/v1/payments/"


def _authenticated(client) -> Customer:
    user = cast(User, UserFactory())
    customer = cast(Customer, CustomerFactory(user_id=user.pk))
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return customer


def _post_json(client, url, payload, *, idempotency_key=None):
    headers = {}
    if idempotency_key is not None:
        headers["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
    return client.post(url, data=json.dumps(payload), content_type="application/json", **headers)


def _pending_order_for(customer_id, *, total_amount):
    return OrderFactory(
        customer_id=customer_id,
        status=OrderStatus.PENDING_PAYMENT.value,
        total_amount=total_amount,
    )


@pytest.mark.django_db
def test_topup_without_an_idempotency_key_is_rejected(client):
    _authenticated(client)

    response = _post_json(
        client, TOPUP_URL, {"amount": "10.00", "payment_method": "cash_on_delivery"}
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_topup_credits_the_wallet_by_the_charged_amount(client):
    _authenticated(client)

    response = _post_json(
        client,
        TOPUP_URL,
        {"amount": "25.00", "payment_method": "cash_on_delivery"},
        idempotency_key="topup-key",
    )

    assert response.status_code == 201
    assert response.json()["balance"] == "25.00"


@pytest.mark.django_db
def test_duplicate_topup_with_the_same_idempotency_key_credits_exactly_once(client):
    _authenticated(client)
    payload = {"amount": "25.00", "payment_method": "cash_on_delivery"}

    first = _post_json(client, TOPUP_URL, payload, idempotency_key="duplicate-topup-key")
    second = _post_json(client, TOPUP_URL, payload, idempotency_key="duplicate-topup-key")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()

    balance = client.get(WALLET_URL)
    assert balance.json()["balance"] == "25.00"
    assert len(balance.json()["transactions"]) == 1


@pytest.mark.django_db
def test_topup_cannot_be_funded_through_the_wallet_itself(client):
    _authenticated(client)

    response = _post_json(
        client,
        TOPUP_URL,
        {"amount": "10.00", "payment_method": "wallet"},
        idempotency_key="self-fund-key",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_top_up_then_pay_with_wallet_at_checkout_succeeds_end_to_end(client):
    """Issue #199 Test Requirements: top-up then pay-with-wallet at checkout end-to-end."""
    customer = _authenticated(client)
    topup = _post_json(
        client,
        TOPUP_URL,
        {"amount": "25.00", "payment_method": "cash_on_delivery"},
        idempotency_key="e2e-topup-key",
    )
    assert topup.status_code == 201
    assert topup.json()["balance"] == "25.00"

    order = _pending_order_for(customer.pk, total_amount=Decimal("18.00"))
    payment = _post_json(
        client,
        PAYMENTS_URL,
        {"order_id": order.pk, "payment_method": "wallet"},
        idempotency_key="e2e-pay-with-wallet-key",
    )

    assert payment.status_code == 201
    assert payment.json()["status"] == "captured"
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED.value

    balance = client.get(WALLET_URL)
    assert balance.status_code == 200
    assert balance.json()["balance"] == "7.00"
    assert len(balance.json()["transactions"]) == 2


@pytest.mark.django_db
def test_paying_with_an_insufficient_wallet_balance_fails_the_order_without_touching_the_ledger(
    client,
):
    """Issue #199 Test Requirements: an insufficient wallet balance correctly results in
    `PAYMENT_FAILED` on the order, not a partial or corrupted state."""
    customer = _authenticated(client)
    _post_json(
        client,
        TOPUP_URL,
        {"amount": "5.00", "payment_method": "cash_on_delivery"},
        idempotency_key="small-topup-key",
    )

    order = _pending_order_for(customer.pk, total_amount=Decimal("18.00"))
    payment = _post_json(
        client,
        PAYMENTS_URL,
        {"order_id": order.pk, "payment_method": "wallet"},
        idempotency_key="pay-with-insufficient-wallet-key",
    )

    assert payment.status_code == 201
    assert payment.json()["status"] == "failed"
    order.refresh_from_db()
    assert order.status == OrderStatus.PAYMENT_FAILED.value

    balance = client.get(WALLET_URL)
    assert balance.json()["balance"] == "5.00"
    assert len(balance.json()["transactions"]) == 1


@pytest.mark.django_db
def test_wallet_balance_is_always_the_authenticated_users_own_never_another_customers(client):
    owner = _authenticated(client)
    _post_json(
        client,
        TOPUP_URL,
        {"amount": "40.00", "payment_method": "cash_on_delivery"},
        idempotency_key="owner-topup-key",
    )

    other_client = Client()
    other_customer = _authenticated(other_client)
    assert other_customer.pk != owner.pk

    response = other_client.get(WALLET_URL)
    assert response.json()["balance"] == "0.00"
    assert response.json()["transactions"] == []
