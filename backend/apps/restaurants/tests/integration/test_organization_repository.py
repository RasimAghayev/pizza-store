import pytest

from apps.restaurants.repositories.organization_repository import OrganizationRepository
from apps.restaurants.tests.factories import OrganizationFactory


@pytest.mark.django_db
def test_create_persists_an_organization():
    repository = OrganizationRepository()

    organization = repository.create(name="Pizza Co", owner_user_id=1)

    assert organization.pk is not None
    assert organization.owner_user_id == 1


@pytest.mark.django_db
def test_get_by_id_returns_none_when_missing():
    assert OrganizationRepository().get_by_id(999_999) is None


@pytest.mark.django_db
def test_filter_by_ids_returns_only_the_requested_organizations():
    wanted = OrganizationFactory()
    OrganizationFactory()

    result = OrganizationRepository().filter_by_ids({wanted.pk})

    assert [org.pk for org in result] == [wanted.pk]


@pytest.mark.django_db
def test_update_persists_the_new_name():
    organization = OrganizationFactory(name="Old Name")

    updated = OrganizationRepository().update(organization, name="New Name")

    organization.refresh_from_db()
    assert updated.name == "New Name"
    assert organization.name == "New Name"


@pytest.mark.django_db
def test_delete_removes_the_row():
    organization = OrganizationFactory()
    organization_id = organization.pk

    OrganizationRepository().delete(organization)

    assert OrganizationRepository().get_by_id(organization_id) is None
