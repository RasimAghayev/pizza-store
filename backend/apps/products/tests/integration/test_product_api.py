import json
from decimal import Decimal
from typing import cast

import pytest

from apps.identity.domain.rbac import RoleCode
from apps.identity.models import User
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.products.tests.factories import (
    AllergenFactory,
    OptionGroupFactory,
    ProductFactory,
    ToppingFactory,
)
from apps.restaurants.tests.factories import OrganizationFactory

PRODUCTS_URL = "/api/v1/products/"


def _authenticated(client, *, role_code: RoleCode, organization_id=None, branch_id=None):
    user = cast(User, UserFactory())
    RoleAssignmentRepository().create(
        user=user, role_code=role_code, organization_id=organization_id, branch_id=branch_id
    )
    token = TokenService().issue_access_token(user)
    client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return user


def _post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _patch_json(client, url, payload):
    return client.patch(url, data=json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_listing_products_requires_an_organization_id_filter(client):
    response = client.get(PRODUCTS_URL)

    assert response.status_code == 400


@pytest.mark.django_db
def test_anonymous_can_list_an_organizations_products(client):
    organization = OrganizationFactory()
    ProductFactory.create_batch(2, organization_id=organization.pk)
    ProductFactory()  # a different organization's product -- must not appear

    response = client.get(PRODUCTS_URL, {"organization_id": organization.pk})

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.django_db
def test_anonymous_can_retrieve_a_single_product(client):
    product = ProductFactory(name="Margherita")

    response = client.get(f"{PRODUCTS_URL}{product.pk}/")

    assert response.status_code == 200
    assert response.json()["name"] == "Margherita"


@pytest.mark.django_db
def test_anonymous_cannot_create_a_product(client):
    organization = OrganizationFactory()

    response = _post_json(
        client,
        PRODUCTS_URL,
        {"organization_id": organization.pk, "name": "Margherita", "base_price": "10.00"},
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_org_owner_can_create_a_product_under_their_own_organization(client):
    organization = OrganizationFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    response = _post_json(
        client,
        PRODUCTS_URL,
        {"organization_id": organization.pk, "name": "Margherita", "base_price": "10.00"},
    )

    assert response.status_code == 201
    assert response.json()["organization_id"] == organization.pk
    assert response.json()["base_price"] == "10.00"


@pytest.mark.django_db
def test_org_owner_cannot_create_a_product_under_a_different_organization(client):
    other_organization = OrganizationFactory()
    own_organization = OrganizationFactory()
    _authenticated(
        client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own_organization.pk
    )

    response = _post_json(
        client,
        PRODUCTS_URL,
        {"organization_id": other_organization.pk, "name": "Margherita", "base_price": "10.00"},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_rejects_an_unknown_organization_id(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(
        client,
        PRODUCTS_URL,
        {"organization_id": 999_999, "name": "Margherita", "base_price": "10.00"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_branch_manager_cannot_update_a_product(client):
    product = ProductFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)

    response = _patch_json(client, f"{PRODUCTS_URL}{product.pk}/", {"name": "Renamed"})

    assert response.status_code == 403


@pytest.mark.django_db
def test_org_owner_can_delete_their_own_product(client):
    organization = OrganizationFactory()
    product = ProductFactory(organization_id=organization.pk)
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    response = client.delete(f"{PRODUCTS_URL}{product.pk}/")

    assert response.status_code == 204


@pytest.mark.django_db
def test_org_owner_can_add_an_option_group_and_choice_to_their_own_product(client):
    organization = OrganizationFactory()
    product = ProductFactory(organization_id=organization.pk)
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    group_response = _post_json(
        client, f"{PRODUCTS_URL}{product.pk}/option-groups/", {"kind": "size"}
    )
    assert group_response.status_code == 201
    group_id = group_response.json()["id"]

    choice_response = _post_json(
        client,
        f"{PRODUCTS_URL}{product.pk}/option-groups/{group_id}/choices/",
        {"name": "Large", "price_delta": "3.00"},
    )
    assert choice_response.status_code == 201
    assert choice_response.json()["price_delta"] == "3.00"


@pytest.mark.django_db
def test_super_admin_can_create_a_topping_in_the_shared_catalog(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(
        client, f"{PRODUCTS_URL}toppings/", {"name": "Pepperoni", "price_delta": "1.50"}
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_org_scoped_owner_cannot_create_a_topping_in_the_shared_catalog(client):
    organization = OrganizationFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    response = _post_json(
        client, f"{PRODUCTS_URL}toppings/", {"name": "Pepperoni", "price_delta": "1.50"}
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_org_owner_can_attach_an_existing_topping_to_their_own_product(client):
    organization = OrganizationFactory()
    product = ProductFactory(organization_id=organization.pk)
    topping = ToppingFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    response = _post_json(
        client,
        f"{PRODUCTS_URL}{product.pk}/toppings/",
        {"topping_id": topping.pk, "is_default_included": True},
    )

    assert response.status_code == 201
    assert response.json()["is_default_included"] is True


@pytest.mark.django_db
def test_product_allergens_union_its_own_and_only_default_included_toppings_allergens(client):
    organization = OrganizationFactory()
    product = ProductFactory(organization_id=organization.pk)
    own_allergen = AllergenFactory(name="Gluten")
    product.allergens.set([own_allergen.pk])

    default_topping = ToppingFactory(name="Mozzarella")
    default_allergen = AllergenFactory(name="Dairy")
    default_topping.allergens.set([default_allergen.pk])

    optional_topping = ToppingFactory(name="Shrimp")
    optional_allergen = AllergenFactory(name="Shellfish")
    optional_topping.allergens.set([optional_allergen.pk])

    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)
    _post_json(
        client,
        f"{PRODUCTS_URL}{product.pk}/toppings/",
        {"topping_id": default_topping.pk, "is_default_included": True},
    )
    _post_json(
        client,
        f"{PRODUCTS_URL}{product.pk}/toppings/",
        {"topping_id": optional_topping.pk, "is_default_included": False},
    )

    response = client.get(f"{PRODUCTS_URL}{product.pk}/allergens/")

    assert response.status_code == 200
    names = {allergen["name"] for allergen in response.json()}
    assert names == {"Gluten", "Dairy"}


@pytest.mark.django_db
def test_price_quote_matches_base_price_plus_option_and_topping_deltas(client):
    organization = OrganizationFactory()
    product = ProductFactory(organization_id=organization.pk, base_price=Decimal("10.00"))
    group = OptionGroupFactory(product=product, kind="size")
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    choice_response = _post_json(
        client,
        f"{PRODUCTS_URL}{product.pk}/option-groups/{group.pk}/choices/",
        {"name": "Large", "price_delta": "3.00"},
    )
    choice_id = choice_response.json()["id"]

    topping = ToppingFactory(price_delta=Decimal("1.50"))
    _post_json(
        client,
        f"{PRODUCTS_URL}{product.pk}/toppings/",
        {"topping_id": topping.pk, "is_default_included": False},
    )

    response = _post_json(
        client,
        f"{PRODUCTS_URL}{product.pk}/price-quote/",
        {"option_choice_ids": [choice_id], "topping_ids": [topping.pk], "quantity": 2},
    )

    assert response.status_code == 200
    # (10.00 + 3.00 + 1.50) * 2 = 29.00
    assert response.json()["price"] == "29.00"


@pytest.mark.django_db
def test_price_quote_for_half_and_half_averages_the_two_products(client):
    first = ProductFactory(base_price=Decimal("10.00"))
    second = ProductFactory(base_price=Decimal("14.00"))

    response = _post_json(
        client,
        f"{PRODUCTS_URL}{first.pk}/price-quote/",
        {"other_half": {"product_id": second.pk}},
    )

    assert response.status_code == 200
    assert response.json()["price"] == "12.00"


@pytest.mark.django_db
def test_price_quote_for_a_topping_not_attached_to_the_product_returns_a_generic_error(client):
    product = ProductFactory()
    topping = ToppingFactory()

    response = _post_json(
        client, f"{PRODUCTS_URL}{product.pk}/price-quote/", {"topping_ids": [topping.pk]}
    )

    assert response.status_code == 400
    # A fixed, generic message -- never the raw internal exception text.
    assert response.json()["error"]["details"] == {
        "non_field_errors": "Invalid price quote selection."
    }
