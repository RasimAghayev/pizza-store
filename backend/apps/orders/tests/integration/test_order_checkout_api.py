import json
from decimal import Decimal
from typing import cast

import pytest
from django.test import Client

from apps.branches.tests.factories import BranchFactory
from apps.cart.services.cart_service import CartService
from apps.customers.models.customer import Customer
from apps.customers.tests.factories import AddressFactory, CustomerFactory
from apps.identity.models import User
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.menu.tests.factories import MenuCategoryFactory, MenuItemFactory
from apps.orders.models import Order
from apps.products.tests.factories import ProductFactory
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory

ORDERS_URL = "/api/v1/orders/"
CHECKOUT_URL = f"{ORDERS_URL}checkout/"


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


def _checkout_ready_cart(customer_id, *, quantity=1, **branch_kwargs):
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant, **branch_kwargs)
    product = ProductFactory(organization_id=organization.pk, base_price=Decimal("10.00"))
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=product, category=category)
    CartService().add_item(
        customer_id=customer_id, branch_id=branch.pk, product_id=product.pk, quantity=quantity
    )
    return branch, product


@pytest.mark.django_db
def test_checkout_without_an_idempotency_key_is_rejected(client):
    customer = _authenticated(client)
    _checkout_ready_cart(customer.pk)
    address = AddressFactory(customer=customer)

    response = _post_json(client, CHECKOUT_URL, {"address_id": address.pk})

    assert response.status_code == 400
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_with_an_empty_cart_is_rejected(client):
    customer = _authenticated(client)
    address = AddressFactory(customer=customer)

    response = _post_json(
        client, CHECKOUT_URL, {"address_id": address.pk}, idempotency_key="empty-cart-key"
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_below_the_branch_minimum_is_rejected(client):
    customer = _authenticated(client)
    _checkout_ready_cart(customer.pk, minimum_order_amount=Decimal("50.00"))
    address = AddressFactory(customer=customer)

    response = _post_json(
        client, CHECKOUT_URL, {"address_id": address.pk}, idempotency_key="below-min-key"
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_rejects_an_unknown_total_field_via_the_strict_serializer(client):
    """Issue #197 Test Requirements: a tampered total/amount field has zero effect because
    the serializer does not even accept it -- `StrictSerializer` rejects it as unknown."""
    customer = _authenticated(client)
    _checkout_ready_cart(customer.pk)
    address = AddressFactory(customer=customer)

    response = _post_json(
        client,
        CHECKOUT_URL,
        {"address_id": address.pk, "total_amount": "0.01"},
        idempotency_key="tampered-key",
    )

    assert response.status_code == 400
    assert Order.objects.count() == 0


@pytest.mark.django_db
def test_checkout_succeeds_and_the_total_is_server_computed(client):
    customer = _authenticated(client)
    branch, _product = _checkout_ready_cart(customer.pk, quantity=2)
    address = AddressFactory(customer=customer)

    response = _post_json(
        client, CHECKOUT_URL, {"address_id": address.pk}, idempotency_key="success-key"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["subtotal"] == "20.00"
    assert body["delivery_fee"] == str(branch.delivery_fee)
    assert body["total_amount"] == str(Decimal("20.00") + branch.delivery_fee)
    assert body["status"] == "pending_payment"
    assert len(body["items"]) == 1


@pytest.mark.django_db
def test_duplicate_checkout_with_the_same_idempotency_key_creates_exactly_one_order(client):
    """The literal Epic #15 acceptance test (Issue #197 Test Requirements)."""
    customer = _authenticated(client)
    _checkout_ready_cart(customer.pk)
    address = AddressFactory(customer=customer)

    first = _post_json(
        client, CHECKOUT_URL, {"address_id": address.pk}, idempotency_key="duplicate-key"
    )
    second = _post_json(
        client, CHECKOUT_URL, {"address_id": address.pk}, idempotency_key="duplicate-key"
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert Order.objects.count() == 1


@pytest.mark.django_db
def test_list_returns_only_the_authenticated_customers_orders(client):
    owner = _authenticated(client)
    _checkout_ready_cart(owner.pk)
    owner_address = AddressFactory(customer=owner)
    _post_json(
        client, CHECKOUT_URL, {"address_id": owner_address.pk}, idempotency_key="list-owner-key"
    )

    other_client = Client()
    other_customer = _authenticated(other_client)
    _checkout_ready_cart(other_customer.pk)
    other_address = AddressFactory(customer=other_customer)
    _post_json(
        other_client,
        CHECKOUT_URL,
        {"address_id": other_address.pk},
        idempotency_key="list-other-key",
    )

    response = client.get(ORDERS_URL)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "pending_payment"


@pytest.mark.django_db
def test_detail_on_another_customers_order_returns_404_not_403(client):
    owner_client = Client()
    owner = _authenticated(owner_client)
    _checkout_ready_cart(owner.pk)
    owner_address = AddressFactory(customer=owner)
    created = _post_json(
        owner_client,
        CHECKOUT_URL,
        {"address_id": owner_address.pk},
        idempotency_key="detail-owner-key",
    )
    order_id = created.json()["id"]

    _authenticated(client)

    response = client.get(f"{ORDERS_URL}{order_id}/")

    assert response.status_code == 404
