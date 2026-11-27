import pytest

from apps.restaurants.repositories.restaurant_repository import RestaurantRepository
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory


@pytest.mark.django_db
def test_create_persists_a_restaurant():
    organization = OrganizationFactory()

    restaurant = RestaurantRepository().create(organization=organization, name="Pizza Palace")

    assert restaurant.pk is not None
    assert restaurant.organization_id == organization.pk


@pytest.mark.django_db
def test_get_by_id_returns_none_when_missing():
    assert RestaurantRepository().get_by_id(999_999) is None


@pytest.mark.django_db
def test_all_returns_every_restaurant_ordered_by_name():
    RestaurantFactory(name="Zeta Pizza")
    RestaurantFactory(name="Alpha Pizza")

    names = [r.name for r in RestaurantRepository().all()]

    assert names == ["Alpha Pizza", "Zeta Pizza"]


@pytest.mark.django_db
def test_update_persists_the_new_fields():
    restaurant = RestaurantFactory(name="Old Name", description="")

    updated = RestaurantRepository().update(restaurant, name="New Name", description="Updated")

    restaurant.refresh_from_db()
    assert updated.description == "Updated"
    assert restaurant.name == "New Name"


@pytest.mark.django_db
def test_delete_removes_the_row():
    restaurant = RestaurantFactory()
    restaurant_id = restaurant.pk

    RestaurantRepository().delete(restaurant)

    assert RestaurantRepository().get_by_id(restaurant_id) is None
