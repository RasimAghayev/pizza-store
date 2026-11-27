import json
from decimal import Decimal
from typing import cast

import pytest
from django.test import Client

from apps.branches.tests.factories import BranchFactory
from apps.customers.models.customer import Customer
from apps.customers.tests.factories import CustomerFactory
from apps.identity.models import User
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.menu.tests.factories import MenuCategoryFactory, MenuItemFactory
from apps.products.tests.factories import ProductFactory
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory

CART_URL = "/api/v1/cart/"


def _authenticated(client) -> Customer:
    user = cast(User, UserFactory())
    customer = cast(Customer, CustomerFactory(user_id=user.pk))
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return customer


def _orderable_branch_and_product(**product_kwargs):
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    product = ProductFactory(organization_id=organization.pk, **product_kwargs)
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=product, category=category)
    return branch, product


def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _patch_json(client, url, payload):
    return client.patch(url, data=json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_get_with_no_cart_returns_the_empty_shape(client):
    _authenticated(client)

    response = client.get(CART_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] is None
    assert body["branch_id"] is None
    assert body["items"] == []
    assert body["total"] == "0.00"


@pytest.mark.django_db
def test_add_list_update_remove_cycle(client):
    _authenticated(client)
    branch, product = _orderable_branch_and_product(base_price=Decimal("10.00"))

    create_response = _post_json(
        client, CART_URL, {"branch_id": branch.pk, "product_id": product.pk, "quantity": 2}
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["branch_id"] == branch.pk
    assert len(created["items"]) == 1
    assert created["items"][0]["unit_price"] == "10.00"
    assert created["items"][0]["line_total"] == "20.00"
    assert created["total"] == "20.00"
    item_id = created["items"][0]["id"]

    list_response = client.get(CART_URL)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == "20.00"

    patch_response = _patch_json(client, f"{CART_URL}items/{item_id}/", {"quantity": 3})
    assert patch_response.status_code == 200
    assert patch_response.json()["items"][0]["quantity"] == 3
    assert patch_response.json()["total"] == "30.00"

    delete_response = client.delete(f"{CART_URL}items/{item_id}/")
    assert delete_response.status_code == 200
    assert delete_response.json()["items"] == []

    clear_response = client.delete(CART_URL)
    assert clear_response.status_code == 204


@pytest.mark.django_db
def test_half_and_half_item_prices_via_a_fresh_quote(client):
    _authenticated(client)
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    first = ProductFactory(organization_id=organization.pk, base_price=Decimal("10.00"))
    second = ProductFactory(organization_id=organization.pk, base_price=Decimal("14.00"))
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=branch, product=first, category=category)
    MenuItemFactory(branch=branch, product=second, category=category)

    response = _post_json(
        client,
        CART_URL,
        {
            "branch_id": branch.pk,
            "half_and_half": {
                "first": {"product_id": first.pk},
                "second": {"product_id": second.pk},
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["items"][0]["unit_price"] == "12.00"


@pytest.mark.django_db
def test_adding_an_unavailable_product_is_rejected(client):
    _authenticated(client)
    branch = BranchFactory()
    product = ProductFactory()

    response = _post_json(client, CART_URL, {"branch_id": branch.pk, "product_id": product.pk})

    assert response.status_code == 400


@pytest.mark.django_db
def test_adding_from_a_different_branch_while_the_cart_has_items_returns_409(client):
    _authenticated(client)
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    first_branch = BranchFactory(restaurant=restaurant)
    second_branch = BranchFactory(restaurant=restaurant)
    first_product = ProductFactory(organization_id=organization.pk)
    second_product = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=first_branch, product=first_product, category=category)
    MenuItemFactory(branch=second_branch, product=second_product, category=category)
    _post_json(client, CART_URL, {"branch_id": first_branch.pk, "product_id": first_product.pk})

    response = _post_json(
        client, CART_URL, {"branch_id": second_branch.pk, "product_id": second_product.pk}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


@pytest.mark.django_db
def test_clearing_then_switching_branch_succeeds(client):
    _authenticated(client)
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    first_branch = BranchFactory(restaurant=restaurant)
    second_branch = BranchFactory(restaurant=restaurant)
    first_product = ProductFactory(organization_id=organization.pk)
    second_product = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    MenuItemFactory(branch=first_branch, product=first_product, category=category)
    MenuItemFactory(branch=second_branch, product=second_product, category=category)
    _post_json(client, CART_URL, {"branch_id": first_branch.pk, "product_id": first_product.pk})

    client.delete(CART_URL)
    response = _post_json(
        client, CART_URL, {"branch_id": second_branch.pk, "product_id": second_product.pk}
    )

    assert response.status_code == 201
    assert response.json()["branch_id"] == second_branch.pk


@pytest.mark.django_db
def test_patch_on_another_customers_cart_item_returns_404_not_403():
    owner_client = Client()
    _authenticated(owner_client)
    branch, product = _orderable_branch_and_product()
    owner_create = _post_json(
        owner_client, CART_URL, {"branch_id": branch.pk, "product_id": product.pk}
    )
    owner_item_id = owner_create.json()["items"][0]["id"]

    attacker_client = Client()
    _authenticated(attacker_client)

    response = _patch_json(attacker_client, f"{CART_URL}items/{owner_item_id}/", {"quantity": 2})

    assert response.status_code == 404
