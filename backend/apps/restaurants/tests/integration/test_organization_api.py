import json
from typing import cast

import pytest

from apps.identity.domain.rbac import RoleCode
from apps.identity.models import User
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.restaurants.tests.factories import OrganizationFactory

ORGANIZATIONS_URL = "/api/v1/restaurants/organizations/"


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
def test_list_requires_authentication(client):
    response = client.get(ORGANIZATIONS_URL)
    assert response.status_code == 401


@pytest.mark.django_db
def test_super_admin_can_create_an_organization(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(client, ORGANIZATIONS_URL, {"name": "Pizza Co", "owner_user_id": 1})

    assert response.status_code == 201
    assert response.json()["name"] == "Pizza Co"


@pytest.mark.django_db
def test_an_org_scoped_user_cannot_create_a_brand_new_organization(client):
    own = OrganizationFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own.pk)

    response = _post_json(client, ORGANIZATIONS_URL, {"name": "New Co", "owner_user_id": 1})

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_rejects_an_unknown_field(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(
        client, ORGANIZATIONS_URL, {"name": "Pizza Co", "owner_user_id": 1, "extra": "nope"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_super_admin_sees_every_organization_in_the_list(client):
    OrganizationFactory.create_batch(3)
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = client.get(ORGANIZATIONS_URL)

    assert len(response.json()) == 3


@pytest.mark.django_db
def test_org_scoped_user_sees_only_their_own_organization_in_the_list(client):
    OrganizationFactory()
    own = OrganizationFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own.pk)

    response = client.get(ORGANIZATIONS_URL)

    assert [org["id"] for org in response.json()] == [own.pk]


@pytest.mark.django_db
def test_org_owner_can_update_their_own_organization(client):
    own = OrganizationFactory(name="Old Name")
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own.pk)

    response = client.patch(
        f"{ORGANIZATIONS_URL}{own.pk}/",
        data=json.dumps({"name": "New Name"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


@pytest.mark.django_db
def test_org_owner_cannot_update_a_different_organization(client):
    other = OrganizationFactory()
    own = OrganizationFactory()
    _authenticated(client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own.pk)

    response = client.patch(
        f"{ORGANIZATIONS_URL}{other.pk}/",
        data=json.dumps({"name": "Hijacked"}),
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_retrieve_a_missing_organization_returns_404(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = client.get(f"{ORGANIZATIONS_URL}999999/")

    assert response.status_code == 404
