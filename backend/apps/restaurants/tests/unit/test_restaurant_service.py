import pytest

from apps.restaurants.services.organization_service import OrganizationNotFoundError
from apps.restaurants.services.restaurant_service import RestaurantNotFoundError, RestaurantService
from apps.restaurants.tests.factories import OrganizationFactory, RestaurantFactory


@pytest.mark.django_db
def test_create_raises_when_the_organization_does_not_exist():
    with pytest.raises(OrganizationNotFoundError):
        RestaurantService().create(organization_id=999_999, name="Pizza Palace")


@pytest.mark.django_db
def test_create_persists_a_restaurant_under_an_existing_organization():
    organization = OrganizationFactory()

    restaurant = RestaurantService().create(organization_id=organization.pk, name="Pizza Palace")

    assert restaurant.pk is not None
    assert restaurant.organization_id == organization.pk


@pytest.mark.django_db
def test_list_all_is_unfiltered_and_returns_every_restaurant():
    RestaurantFactory.create_batch(2)

    assert len(RestaurantService().list_all()) == 2


@pytest.mark.django_db
def test_update_raises_when_the_restaurant_does_not_exist():
    with pytest.raises(RestaurantNotFoundError):
        RestaurantService().update(999_999, name="New Name")


@pytest.mark.django_db
def test_delete_raises_when_the_restaurant_does_not_exist():
    with pytest.raises(RestaurantNotFoundError):
        RestaurantService().delete(999_999)
