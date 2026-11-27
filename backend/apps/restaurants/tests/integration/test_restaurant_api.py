import json
from typing import cast

import pytest

from apps.identity.domain.rbac import RoleCode
from apps.identity.models import User
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory

RESTAURANTS_URL = "/api/v1/restaurants/"


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


@pytest.mark.django_db
def test_anonymous_can_list_restaurants(client):
    RestaurantFactory.create_batch(2)

    response = client.get(RESTAURANTS_URL)

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.django_db
def test_anonymous_can_retrieve_a_single_restaurant(client):
    restaurant = RestaurantFactory()

    response = client.get(f"{RESTAURANTS_URL}{restaurant.pk}/")

    assert response.status_code == 200
    assert response.json()["name"] == restaurant.name


@pytest.mark.django_db
def test_anonymous_cannot_create_a_restaurant(client):
    organization = OrganizationFactory()

    response = _post_json(
        client, RESTAURANTS_URL, {"organization_id": organization.pk, "name": "Pizza Palace"}
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_org_owner_can_create_a_restaurant_under_their_own_organization(client):
    organization = OrganizationFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    response = _post_json(
        client, RESTAURANTS_URL, {"organization_id": organization.pk, "name": "Pizza Palace"}
    )

    assert response.status_code == 201
    assert response.json()["organization_id"] == organization.pk


@pytest.mark.django_db
def test_org_owner_cannot_create_a_restaurant_under_a_different_organization(client):
    other_organization = OrganizationFactory()
    own_organization = OrganizationFactory()
    _authenticated(
        client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own_organization.pk
    )

    response = _post_json(
        client, RESTAURANTS_URL, {"organization_id": other_organization.pk, "name": "Pizza Palace"}
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_rejects_an_unknown_organization_id(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(client, RESTAURANTS_URL, {"organization_id": 999_999, "name": "Pizza"})

    assert response.status_code == 400


@pytest.mark.django_db
def test_branch_manager_cannot_update_a_restaurant(client):
    restaurant = RestaurantFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)

    response = client.patch(
        f"{RESTAURANTS_URL}{restaurant.pk}/",
        data=json.dumps({"name": "Renamed"}),
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_org_owner_can_delete_their_own_restaurant(client):
    organization = OrganizationFactory()
    restaurant = RestaurantFactory(organization=organization)
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=organization.pk)

    response = client.delete(f"{RESTAURANTS_URL}{restaurant.pk}/")

    assert response.status_code == 204
