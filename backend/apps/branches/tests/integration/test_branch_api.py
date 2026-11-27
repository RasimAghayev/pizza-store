import json
from datetime import datetime, timezone
from typing import cast

import pytest

from apps.branches.tests.factories import BranchFactory
from apps.identity.domain.rbac import RoleCode
from apps.identity.models import User
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory
from apps.restaurants.tests.factories import RestaurantFactory

BRANCHES_URL = "/api/v1/branches/"


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


def _branch_payload(restaurant_id: int, **overrides):
    payload = {
        "restaurant_id": restaurant_id,
        "name": "Downtown",
        "address": "1 Main St",
        "latitude": "40.7",
        "longitude": "-73.9",
        "phone": "+10000000000",
        "delivery_radius_km": "5.00",
        "delivery_fee": "2.50",
        "minimum_order_amount": "10.00",
        "average_prep_time_minutes": 20,
        "capacity": 50,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_anonymous_can_list_branches(client):
    BranchFactory.create_batch(2)

    response = client.get(BRANCHES_URL)

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.django_db
def test_anonymous_can_retrieve_a_single_branch(client):
    branch = BranchFactory()

    response = client.get(f"{BRANCHES_URL}{branch.pk}/")

    assert response.status_code == 200
    assert response.json()["name"] == branch.name


@pytest.mark.django_db
def test_anonymous_cannot_create_a_branch(client):
    restaurant = RestaurantFactory()

    response = _post_json(client, BRANCHES_URL, _branch_payload(restaurant.pk))

    assert response.status_code == 401


@pytest.mark.django_db
def test_anonymous_cannot_update_a_branch(client):
    branch = BranchFactory()

    response = client.patch(
        f"{BRANCHES_URL}{branch.pk}/",
        data=json.dumps({"name": "Renamed"}),
        content_type="application/json",
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_org_owner_can_create_a_branch_under_their_own_organization(client):
    restaurant = RestaurantFactory()
    _authenticated(
        client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=restaurant.organization_id
    )

    response = _post_json(client, BRANCHES_URL, _branch_payload(restaurant.pk))

    assert response.status_code == 201
    assert response.json()["restaurant_id"] == restaurant.pk


@pytest.mark.django_db
def test_create_rejects_an_unknown_restaurant_id(client):
    _authenticated(client, role_code=RoleCode.SUPER_ADMIN)

    response = _post_json(client, BRANCHES_URL, _branch_payload(999_999))

    assert response.status_code == 400


@pytest.mark.django_db
def test_create_rejects_an_unknown_field(client):
    restaurant = RestaurantFactory()
    _authenticated(
        client, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=restaurant.organization_id
    )

    response = _post_json(client, BRANCHES_URL, _branch_payload(restaurant.pk, extra="nope"))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_branch_manager_can_update_their_own_branch(client):
    branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)

    response = client.patch(
        f"{BRANCHES_URL}{branch.pk}/",
        data=json.dumps({"capacity": 80}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["capacity"] == 80


@pytest.mark.django_db
def test_branch_manager_assigned_to_one_branch_gets_403_editing_a_different_branch(client):
    """Epic #14 Acceptance Criterion #4's first real resource to prove multi-tenant data
    isolation against (Issue #180's own Test Requirements) -- scoped via
    TwoStepPermission's step 2, not merely a 404 that would leak whether the other branch
    exists."""
    branch_a = BranchFactory()
    branch_b = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch_a.pk)

    response = client.patch(
        f"{BRANCHES_URL}{branch_b.pk}/",
        data=json.dumps({"capacity": 999}),
        content_type="application/json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_branch_manager_cannot_create_a_new_branch(client):
    """A branch-scoped grant (branch_id=X) can never match a not-yet-saved Branch's `pk`
    (None) -- only an org-scoped or unscoped holder of `branches.edit` can open a new
    branch, per Issue #180's Implementation Prompt."""
    restaurant = RestaurantFactory()
    existing_branch = BranchFactory(restaurant=restaurant)
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=existing_branch.pk)

    response = _post_json(client, BRANCHES_URL, _branch_payload(restaurant.pk))

    assert response.status_code == 403


@pytest.mark.django_db
def test_branch_manager_assigned_elsewhere_cannot_delete_another_branch(client):
    branch_a = BranchFactory()
    branch_b = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch_a.pk)

    response = client.delete(f"{BRANCHES_URL}{branch_b.pk}/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_retrieve_a_missing_branch_returns_404(client):
    response = client.get(f"{BRANCHES_URL}999999/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_is_open_endpoint_is_public_and_reflects_business_hours(client):
    branch = BranchFactory(is_active=False)

    response = client.get(f"{BRANCHES_URL}{branch.pk}/is-open/")

    assert response.status_code == 200
    assert response.json() == {"is_open": False}


@pytest.mark.django_db
def test_anonymous_can_list_hours(client):
    branch = BranchFactory()

    response = client.get(f"{BRANCHES_URL}{branch.pk}/hours/")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_branch_manager_can_set_their_own_branchs_hours(client):
    branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)

    response = _post_json(
        client,
        f"{BRANCHES_URL}{branch.pk}/hours/",
        {"weekday": 0, "opens_at": "09:00:00", "closes_at": "22:00:00"},
    )

    assert response.status_code == 201
    assert response.json()["weekday"] == 0


@pytest.mark.django_db
def test_hours_rejects_an_overnight_window(client):
    branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)

    response = _post_json(
        client,
        f"{BRANCHES_URL}{branch.pk}/hours/",
        {"weekday": 0, "opens_at": "22:00:00", "closes_at": "02:00:00"},
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_branch_manager_assigned_elsewhere_cannot_set_hours_for_another_branch(client):
    branch_a = BranchFactory()
    branch_b = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch_a.pk)

    response = _post_json(
        client,
        f"{BRANCHES_URL}{branch_b.pk}/hours/",
        {"weekday": 0, "opens_at": "09:00:00", "closes_at": "22:00:00"},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_anonymous_can_list_closures(client):
    branch = BranchFactory()

    response = client.get(f"{BRANCHES_URL}{branch.pk}/closures/")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.django_db
def test_branch_manager_can_add_a_closure_for_their_own_branch(client):
    branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)

    response = _post_json(
        client,
        f"{BRANCHES_URL}{branch.pk}/closures/",
        {
            "starts_at": datetime(2026, 12, 25, tzinfo=timezone.utc).isoformat(),
            "ends_at": datetime(2026, 12, 26, tzinfo=timezone.utc).isoformat(),
            "reason": "Christmas",
        },
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_closures_rejects_an_end_before_start(client):
    branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)

    response = _post_json(
        client,
        f"{BRANCHES_URL}{branch.pk}/closures/",
        {
            "starts_at": datetime(2026, 12, 26, tzinfo=timezone.utc).isoformat(),
            "ends_at": datetime(2026, 12, 25, tzinfo=timezone.utc).isoformat(),
        },
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_branch_manager_can_delete_their_own_branchs_closure(client):
    branch = BranchFactory()
    _authenticated(client, role_code=RoleCode.BRANCH_MANAGER, branch_id=branch.pk)
    create_response = _post_json(
        client,
        f"{BRANCHES_URL}{branch.pk}/closures/",
        {
            "starts_at": datetime(2026, 12, 25, tzinfo=timezone.utc).isoformat(),
            "ends_at": datetime(2026, 12, 26, tzinfo=timezone.utc).isoformat(),
        },
    )
    closure_id = create_response.json()["id"]

    response = client.delete(f"{BRANCHES_URL}{branch.pk}/closures/{closure_id}/")

    assert response.status_code == 204


@pytest.mark.django_db
def test_nearby_returns_only_branches_within_their_own_delivery_radius(client):
    BranchFactory(latitude="40.730610", longitude="-73.935242", delivery_radius_km="5.00")
    BranchFactory(latitude="34.052235", longitude="-118.243683", delivery_radius_km="5.00")

    response = client.get(f"{BRANCHES_URL}nearby/?lat=40.730610&lon=-73.935242")

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.django_db
def test_nearby_requires_lat_and_lon(client):
    response = client.get(f"{BRANCHES_URL}nearby/")

    assert response.status_code == 400
