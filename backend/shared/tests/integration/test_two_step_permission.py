from dataclasses import dataclass

import pytest
from django.core.exceptions import ImproperlyConfigured

import apps.identity.domain.rbac as rbac
from apps.identity.domain.rbac import RoleCode
from apps.identity.services.role_assignment_service import RoleAssignmentService
from apps.identity.tests.factories import UserFactory
from shared.permissions.base import TwoStepPermission

TEST_PERMISSION = "branches.edit"


@dataclass
class _FakeRequest:
    user: object


class _FakeBranchView:
    required_permission = TEST_PERMISSION

    def scope_organization_id(self, obj):
        return obj.get("organization_id")

    def scope_branch_id(self, obj):
        return obj.get("branch_id")


class _NoScopeHooksView:
    required_permission = TEST_PERMISSION


@pytest.fixture(autouse=True)
def _grant_test_permission_to_branch_and_org_roles(monkeypatch):
    """BRANCH_MANAGER/ORGANIZATION_OWNER carry no real permission yet (Issue #175 ships with
    no module exercising step 2 for real) -- temporarily grants this one permission so this
    test can prove TwoStepPermission's scope logic end-to-end against real DB-backed role
    assignments, without adding a speculative permission to production ROLE_PERMISSIONS."""
    patched = dict(rbac.ROLE_PERMISSIONS)
    patched[RoleCode.BRANCH_MANAGER] = frozenset({TEST_PERMISSION})
    patched[RoleCode.ORGANIZATION_OWNER] = frozenset({TEST_PERMISSION})
    patched[RoleCode.SUPER_ADMIN] = frozenset({TEST_PERMISSION})
    monkeypatch.setattr(rbac, "ROLE_PERMISSIONS", patched)


@pytest.mark.django_db
def test_denies_a_user_with_no_matching_permission():
    user = UserFactory()
    RoleAssignmentService().assign(user=user, role_code=RoleCode.CUSTOMER)

    assert TwoStepPermission().has_permission(_FakeRequest(user), _FakeBranchView()) is False


@pytest.mark.django_db
def test_has_permission_allows_a_user_holding_the_permission_in_any_scope():
    user = UserFactory()
    RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)

    assert TwoStepPermission().has_permission(_FakeRequest(user), _FakeBranchView()) is True


@pytest.mark.django_db
def test_object_permission_denies_mismatched_branch_scope():
    user = UserFactory()
    RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
    other_branch_resource = {"organization_id": None, "branch_id": 2}

    allowed = TwoStepPermission().has_object_permission(
        _FakeRequest(user), _FakeBranchView(), other_branch_resource
    )

    assert allowed is False


@pytest.mark.django_db
def test_object_permission_allows_matching_branch_scope():
    user = UserFactory()
    RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
    own_branch_resource = {"organization_id": None, "branch_id": 1}

    allowed = TwoStepPermission().has_object_permission(
        _FakeRequest(user), _FakeBranchView(), own_branch_resource
    )

    assert allowed is True


@pytest.mark.django_db
def test_object_permission_allows_a_branch_manager_scoped_to_multiple_branches():
    """Proves the multi-scope case session_service.py's _claims_for comment calls out: the
    JWT's own org_id/branch_id claim would be null here (two scoped assignments), but
    TwoStepPermission re-derives from the database, not the JWT, so both branches work."""
    user = UserFactory()
    service = RoleAssignmentService()
    service.assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
    service.assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=2)

    for branch_id in (1, 2):
        resource = {"organization_id": None, "branch_id": branch_id}
        assert TwoStepPermission().has_object_permission(
            _FakeRequest(user), _FakeBranchView(), resource
        )


@pytest.mark.django_db
def test_object_permission_org_scoped_role_matches_any_branch_under_that_org():
    user = UserFactory()
    RoleAssignmentService().assign(
        user=user, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=7
    )
    resource = {"organization_id": 7, "branch_id": 99}

    allowed = TwoStepPermission().has_object_permission(
        _FakeRequest(user), _FakeBranchView(), resource
    )

    assert allowed is True


@pytest.mark.django_db
def test_object_permission_unscoped_role_matches_any_resource():
    user = UserFactory()
    RoleAssignmentService().assign(user=user, role_code=RoleCode.SUPER_ADMIN)
    resource = {"organization_id": 123, "branch_id": 456}

    allowed = TwoStepPermission().has_object_permission(
        _FakeRequest(user), _FakeBranchView(), resource
    )

    assert allowed is True


@pytest.mark.django_db
def test_object_permission_ignores_a_forged_scope_elsewhere_and_uses_the_resource_only():
    """ADR 0006: scope is always re-derived from the resource, never trusted from the client."""
    user = UserFactory()
    RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
    forged_resource = {"organization_id": None, "branch_id": 1, "client_claimed_branch_id": 999}

    allowed = TwoStepPermission().has_object_permission(
        _FakeRequest(user), _FakeBranchView(), forged_resource
    )

    assert allowed is True  # matches the resource's real branch_id (1), not the forged field


@pytest.mark.django_db
def test_object_permission_fails_closed_when_view_has_no_scope_hooks():
    user = UserFactory()
    RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)

    with pytest.raises(ImproperlyConfigured):
        TwoStepPermission().has_object_permission(
            _FakeRequest(user), _NoScopeHooksView(), {"branch_id": 1}
        )


def test_denies_an_unauthenticated_request():
    assert TwoStepPermission().has_permission(_FakeRequest(None), _FakeBranchView()) is False
