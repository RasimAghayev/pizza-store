import pytest

from apps.identity.domain.rbac import RoleCode
from apps.identity.services.role_assignment_service import (
    InvalidRoleScopeError,
    RoleAssignmentService,
)
from apps.identity.tests.factories import UserFactory


@pytest.mark.django_db
def test_assign_branch_scoped_role_requires_a_branch_id():
    user = UserFactory()

    with pytest.raises(InvalidRoleScopeError):
        RoleAssignmentService().assign(user=user, role_code=RoleCode.BRANCH_MANAGER)


@pytest.mark.django_db
def test_assign_organization_scoped_role_requires_an_organization_id():
    user = UserFactory()

    with pytest.raises(InvalidRoleScopeError):
        RoleAssignmentService().assign(user=user, role_code=RoleCode.ORGANIZATION_OWNER)


@pytest.mark.django_db
def test_assign_customer_facing_role_rejects_a_scope():
    user = UserFactory()

    with pytest.raises(InvalidRoleScopeError):
        RoleAssignmentService().assign(user=user, role_code=RoleCode.CUSTOMER, branch_id=1)


@pytest.mark.django_db
def test_assign_branch_scoped_role_with_a_branch_id_succeeds():
    user = UserFactory()

    assignment = RoleAssignmentService().assign(
        user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=42
    )

    assert assignment.pk is not None
    assert assignment.branch_id == 42


@pytest.mark.django_db
def test_assign_customer_role_with_no_scope_succeeds():
    user = UserFactory()

    assignment = RoleAssignmentService().assign(user=user, role_code=RoleCode.CUSTOMER)

    assert assignment.organization_id is None
    assert assignment.branch_id is None


@pytest.mark.django_db
def test_roles_for_returns_every_assignment_a_user_holds():
    user = UserFactory()
    service = RoleAssignmentService()
    service.assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
    service.assign(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=2)

    assignments = service.roles_for(user.pk)

    assert {a.branch_id for a in assignments} == {1, 2}
