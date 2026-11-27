import pytest

from apps.identity.domain.rbac import RoleCode
from apps.identity.repositories.role_assignment_repository import RoleAssignmentRepository
from apps.identity.tests.factories import UserFactory
from apps.restaurants.services.organization_service import (
    OrganizationNotFoundError,
    OrganizationService,
)
from apps.restaurants.tests.factories import OrganizationFactory


@pytest.mark.django_db
def test_create_persists_an_organization():
    organization = OrganizationService().create(name="Pizza Co", owner_user_id=1)

    assert organization.pk is not None
    assert organization.name == "Pizza Co"


@pytest.mark.django_db
def test_update_raises_when_the_organization_does_not_exist():
    with pytest.raises(OrganizationNotFoundError):
        OrganizationService().update(999_999, name="New Name")


@pytest.mark.django_db
def test_delete_raises_when_the_organization_does_not_exist():
    with pytest.raises(OrganizationNotFoundError):
        OrganizationService().delete(999_999)


@pytest.mark.django_db
def test_list_visible_to_returns_every_organization_for_an_unscoped_grant():
    OrganizationFactory.create_batch(3)
    user = UserFactory()
    RoleAssignmentRepository().create(user=user, role_code=RoleCode.SUPER_ADMIN)

    visible = OrganizationService().list_visible_to(user)

    assert len(visible) == 3


@pytest.mark.django_db
def test_list_visible_to_returns_only_the_users_own_organization_for_an_org_scoped_grant():
    own = OrganizationFactory()
    OrganizationFactory()  # another organization the user should not see
    user = UserFactory()
    RoleAssignmentRepository().create(
        user=user, role_code=RoleCode.ORGANIZATION_OWNER, organization_id=own.pk
    )

    visible = OrganizationService().list_visible_to(user)

    assert [org.pk for org in visible] == [own.pk]


@pytest.mark.django_db
def test_list_visible_to_returns_nothing_for_a_purely_branch_scoped_grant():
    OrganizationFactory()
    user = UserFactory()
    RoleAssignmentRepository().create(user=user, role_code=RoleCode.BRANCH_MANAGER, branch_id=1)

    visible = OrganizationService().list_visible_to(user)

    assert visible == []
