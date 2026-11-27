import json
from typing import cast

import pytest

from apps.customers.models.address import Address
from apps.customers.tests.factories import AddressFactory, CustomerFactory
from apps.identity.models import User
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory

ADDRESSES_URL = "/api/v1/customers/me/addresses/"


def _authenticated(client):
    user = cast(User, UserFactory())
    customer = CustomerFactory(user_id=user.pk)
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return customer


def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _patch_json(client, url, payload):
    return client.patch(url, data=json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_create_without_gps_coordinates_succeeds(client):
    _authenticated(client)

    response = _post_json(
        client, ADDRESSES_URL, {"street_and_unit": "1 Pine St", "city": "Springfield"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["latitude"] is None
    assert body["longitude"] is None


@pytest.mark.django_db
def test_create_with_gps_coordinates_succeeds(client):
    _authenticated(client)

    response = _post_json(
        client,
        ADDRESSES_URL,
        {
            "street_and_unit": "1 Pine St",
            "city": "Springfield",
            "latitude": "40.730610",
            "longitude": "-73.935242",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["latitude"] == "40.730610"
    assert body["longitude"] == "-73.935242"


@pytest.mark.django_db
def test_list_returns_only_the_requesting_customers_addresses(client):
    customer = _authenticated(client)
    AddressFactory(customer=customer)
    AddressFactory()  # a different customer's address

    response = client.get(ADDRESSES_URL)

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_detail_for_another_customers_address_returns_404_not_403(client):
    other_customer = CustomerFactory()
    other_address = AddressFactory(customer=other_customer)
    _authenticated(client)

    response = client.get(f"{ADDRESSES_URL}{other_address.pk}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_patch_on_another_customers_address_returns_404_not_403(client):
    other_customer = CustomerFactory()
    other_address = AddressFactory(customer=other_customer)
    _authenticated(client)

    response = _patch_json(client, f"{ADDRESSES_URL}{other_address.pk}/", {"city": "Shelbyville"})

    assert response.status_code == 404
    other_address.refresh_from_db()
    assert other_address.city != "Shelbyville"


@pytest.mark.django_db
def test_delete_removes_the_address(client):
    customer = _authenticated(client)
    address = AddressFactory(customer=customer)

    response = client.delete(f"{ADDRESSES_URL}{address.pk}/")

    assert response.status_code == 204
    assert not Address.objects.filter(pk=address.pk).exists()


@pytest.mark.django_db
def test_exactly_one_address_stays_default_after_a_third_is_set_default(client):
    customer = _authenticated(client)
    first = AddressFactory(customer=customer, is_default=True)
    AddressFactory(customer=customer, is_default=False)
    third = AddressFactory(customer=customer, is_default=False)

    response = _patch_json(client, f"{ADDRESSES_URL}{third.pk}/", {"is_default": True})

    assert response.status_code == 200
    assert Address.objects.filter(customer=customer, is_default=True).count() == 1
    first.refresh_from_db()
    assert first.is_default is False
    third.refresh_from_db()
    assert third.is_default is True
