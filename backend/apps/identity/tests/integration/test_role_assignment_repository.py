import pytest
from django.db import IntegrityError

from apps.identity.domain.rbac import RoleCode
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.tests.factories import UserFactory


@pytest.mark.django_db
def test_create_persists_a_role_assignment():
    user = UserFactory()
    repository = RoleAssignmentRepository()

    assignment = repository.create(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)

    assert assignment.pk is not None
    assert assignment.role_code == RoleCode.BRANCH_MANAGER


@pytest.mark.django_db
def test_for_user_returns_only_that_users_assignments():
    repository = RoleAssignmentRepository()
    user_a, user_b = UserFactory(), UserFactory()
    repository.create(user=user_a, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
    repository.create(user=user_b, role_code=RoleCode.BRANCH_MANAGER, branch_id=2)

    assignments = repository.for_user(user_a.pk)

    assert len(assignments) == 1
    assert assignments[0].user_id == user_a.pk


@pytest.mark.django_db
def test_has_role_is_true_only_for_an_existing_assignment():
    user = UserFactory()
    repository = RoleAssignmentRepository()
    repository.create(user=user, role_code=RoleCode.CUSTOMER)

    assert repository.has_role(user_id=user.pk, role_code=RoleCode.CUSTOMER) is True
    assert repository.has_role(user_id=user.pk, role_code=RoleCode.VERIFIED_CUSTOMER) is False


@pytest.mark.django_db
def test_duplicate_assignment_same_scope_is_rejected():
    user = UserFactory()
    repository = RoleAssignmentRepository()
    repository.create(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)

    with pytest.raises(IntegrityError):
        repository.create(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)
