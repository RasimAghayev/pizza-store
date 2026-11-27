import json
from typing import cast

import pytest

from apps.branches.tests.factories import BranchFactory
from apps.identity.domain.rbac import RoleCode
from apps.identity.models import User
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.menu.tests.factories import MenuCategoryFactory, MenuItemFactory
from apps.products.tests.factories import ProductFactory
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory

MENU_URL = "/api/v1/menu/"


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


def _branch_product_category_under_same_organization():
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    branch = BranchFactory(restaurant=restaurant)
    product = ProductFactory(organization_id=organization.pk)
    category = MenuCategoryFactory(organization_id=organization.pk)
    return organization, branch, product, category


@pytest.mark.django_db
def test_branch_menu_lists_only_that_branchs_available_items(client):
    organization, branch, product, category = _branch_product_category_under_same_organization()
    other_branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)
    create_response = _post_json(
        client,
        f"{MENU_URL}items/",
        {"branch_id": branch.pk, "product_id": product.pk, "category_id": category.pk},
    )
    assert create_response.status_code == 201
    client.defaults.pop("HTTP_AUTHORIZATION", None)

    response = client.get(f"/api/v1/branches/{branch.pk}/menu/")
    other_response = client.get(f"/api/v1/branches/{other_branch.pk}/menu/")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["product_id"] == product.pk
    assert other_response.status_code == 200
    assert other_response.json() == []


@pytest.mark.django_db
def test_branch_menu_for_a_missing_branch_returns_404(client):
    response = client.get("/api/v1/branches/999999/menu/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_branch_menu_excludes_an_unavailable_item(client):
    item = MenuItemFactory(is_available=False)

    response = client.get(f"/api/v1/branches/{item.branch_id}/menu/")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_anonymous_cannot_create_a_category(client):
    organization = OrganizationFactory()

    response = _post_json(
        client, f"{MENU_URL}categories/", {"organization_id": organization.pk, "name": "Pizzas"}
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_org_owner_can_create_a_category_under_their_own_organization(client):
    organization = OrganizationFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    response = _post_json(
        client, f"{MENU_URL}categories/", {"organization_id": organization.pk, "name": "Pizzas"}
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Pizzas"


@pytest.mark.django_db
def test_org_owner_cannot_create_a_category_under_a_different_organization(client):
    own_organization = OrganizationFactory()
    other_organization = OrganizationFactory()
    _authenticated(
        client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own_organization.pk
    )

    response = _post_json(
        client,
        f"{MENU_URL}categories/",
        {"organization_id": other_organization.pk, "name": "Pizzas"},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_branch_manager_cannot_create_a_category(client):
    """MenuCategory is org-wide (`scope_branch_id` always None) -- a purely branch-scoped
    grant can never satisfy TwoStepPermission's step 2 for it, same structural rule already
    established for Product (Issue #181)."""
    branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)

    response = _post_json(
        client,
        f"{MENU_URL}categories/",
        {"organization_id": branch.restaurant.organization_id, "name": "Pizzas"},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_category_list_requires_organization_id(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = client.get(f"{MENU_URL}categories/")

    assert response.status_code == 400


@pytest.mark.django_db
def test_branch_manager_can_add_an_item_to_their_own_branchs_menu(client):
    organization, branch, product, category = _branch_product_category_under_same_organization()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)

    response = _post_json(
        client,
        f"{MENU_URL}items/",
        {"branch_id": branch.pk, "product_id": product.pk, "category_id": category.pk},
    )

    assert response.status_code == 201
    assert response.json()["branch_id"] == branch.pk
    assert response.json()["product_id"] == product.pk


@pytest.mark.django_db
def test_branch_manager_assigned_elsewhere_cannot_add_an_item_to_another_branch(client):
    organization, branch, product, category = _branch_product_category_under_same_organization()
    other_branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=other_branch.pk)

    response = _post_json(
        client,
        f"{MENU_URL}items/",
        {"branch_id": branch.pk, "product_id": product.pk, "category_id": category.pk},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_item_rejects_an_unknown_branch_id(client):
    _, _, product, category = _branch_product_category_under_same_organization()
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(
        client,
        f"{MENU_URL}items/",
        {"branch_id": 999_999, "product_id": product.pk, "category_id": category.pk},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_item_rejects_a_product_from_a_different_organization(client):
    _, branch, _, category = _branch_product_category_under_same_organization()
    other_product = ProductFactory()
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(
        client,
        f"{MENU_URL}items/",
        {"branch_id": branch.pk, "product_id": other_product.pk, "category_id": category.pk},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_item_rejects_a_duplicate_branch_product_pair(client):
    _, branch, product, category = _branch_product_category_under_same_organization()
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)
    payload = {"branch_id": branch.pk, "product_id": product.pk, "category_id": category.pk}
    first = _post_json(client, f"{MENU_URL}items/", payload)
    assert first.status_code == 201

    response = _post_json(client, f"{MENU_URL}items/", payload)

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_item_rejects_an_unknown_field(client):
    _, branch, product, category = _branch_product_category_under_same_organization()
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(
        client,
        f"{MENU_URL}items/",
        {
            "branch_id": branch.pk,
            "product_id": product.pk,
            "category_id": category.pk,
            "extra": "nope",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_item_list_requires_branch_id(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = client.get(f"{MENU_URL}items/")

    assert response.status_code == 400


@pytest.mark.django_db
def test_item_list_includes_unavailable_items_for_staff(client):
    """Issue #182's own Test Requirement: marking `is_available=False` removes an item from
    the public listing but not from staff's own item list."""
    item = MenuItemFactory(is_available=False)
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=item.branch_id)

    response = client.get(f"{MENU_URL}items/?branch_id={item.branch_id}")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["is_available"] is False


@pytest.mark.django_db
def test_branch_manager_can_toggle_availability_for_their_own_branchs_item(client):
    item = MenuItemFactory(is_available=True)
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=item.branch_id)

    response = _patch_json(client, f"{MENU_URL}items/{item.pk}/", {"is_available": False})

    assert response.status_code == 200
    assert response.json()["is_available"] is False


@pytest.mark.django_db
def test_branch_manager_assigned_elsewhere_cannot_update_another_branchs_item(client):
    item = MenuItemFactory()
    other_branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=other_branch.pk)

    response = _patch_json(client, f"{MENU_URL}items/{item.pk}/", {"is_available": False})

    assert response.status_code == 403


@pytest.mark.django_db
def test_branch_manager_can_delete_their_own_branchs_item(client):
    item = MenuItemFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=item.branch_id)

    response = client.delete(f"{MENU_URL}items/{item.pk}/")

    assert response.status_code == 204


@pytest.mark.django_db
def test_item_detail_for_a_missing_item_returns_404(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = client.get(f"{MENU_URL}items/999999/")

    assert response.status_code == 404
