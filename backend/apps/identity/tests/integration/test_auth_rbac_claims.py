import json

import pytest
from django.core.cache import cache

from apps.identity.domain.rbac import RoleCode
from apps.identity.services.role_assignment_service import RoleAssignmentService
from apps.identity.services.token_service import TokenService
from apps.identity.tests.factories import UserFactory

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


def _post(client, url, payload):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_CLIENT_TYPE="native",
    )


@pytest.mark.django_db
def test_login_populates_roles_and_branch_scope_for_a_branch_scoped_staff_user(client):
    user = UserFactory(password=PASSWORD)
    RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=7)

    body = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD}).json()
    claims = TokenService().verify_access_token(body["access_token"])

    assert claims["roles"] == [RoleCode.BRANCH_MANAGER.value]
    assert claims["branch_id"] == 7
    assert claims["org_id"] is None


@pytest.mark.django_db
def test_login_leaves_scope_null_for_a_user_with_no_role_assignments(client):
    user = UserFactory(password=PASSWORD)

    body = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD}).json()
    claims = TokenService().verify_access_token(body["access_token"])

    assert claims["roles"] == []
    assert claims["org_id"] is None
    assert claims["branch_id"] is None


@pytest.mark.django_db
def test_login_leaves_scope_null_when_the_user_holds_multiple_scoped_assignments(client):
    """Ambiguous single-claim case (ADR 0006 session_service.py::_claims_for) -- every real
    authorization decision re-derives per-assignment scope at request time instead."""
    user = UserFactory(password=PASSWORD)
    service = RoleAssignmentService()
    service.assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
    service.assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=2)

    body = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD}).json()
    claims = TokenService().verify_access_token(body["access_token"])

    assert set(claims["roles"]) == {RoleCode.BRANCH_MANAGER.value}
    assert claims["branch_id"] is None


@pytest.mark.django_db
def test_refresh_carries_the_original_roles_and_scope_forward(client):
    user = UserFactory(password=PASSWORD)
    RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=7)
    login_body = _post(client, LOGIN_URL, {"email": user.email, "password": PASSWORD}).json()

    refresh_body = _post(client, REFRESH_URL, {"refresh_token": login_body["refresh_token"]}).json()
    claims = TokenService().verify_access_token(refresh_body["access_token"])

    assert claims["roles"] == [RoleCode.BRANCH_MANAGER.value]
    assert claims["branch_id"] == 7
