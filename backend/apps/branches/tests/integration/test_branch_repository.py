from decimal import Decimal

import pytest

from apps.branches.repositories.branch_repository import BranchRepository
from apps.branches.tests.factories import BranchFactory
from apps.restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
def test_create_persists_a_branch():
    restaurant = RestaurantFactory()

    branch = BranchRepository().create(
        restaurant_id=restaurant.pk,
        name="Downtown",
        address="1 Main St",
        latitude=Decimal("40.7"),
        longitude=Decimal("-73.9"),
        phone="+10000000000",
        delivery_radius_km=Decimal("5"),
        delivery_fee=Decimal("2.5"),
        minimum_order_amount=Decimal("10"),
        average_prep_time_minutes=20,
        capacity=50,
    )

    assert branch.pk is not None
    assert branch.restaurant_id == restaurant.pk


@pytest.mark.django_db
def test_get_by_id_returns_none_when_missing():
    assert BranchRepository().get_by_id(999_999) is None


@pytest.mark.django_db
def test_filter_by_restaurant_returns_only_that_restaurants_branches():
    restaurant_a, restaurant_b = RestaurantFactory(), RestaurantFactory()
    wanted = BranchFactory(restaurant=restaurant_a)
    BranchFactory(restaurant=restaurant_b)

    result = BranchRepository().filter_by_restaurant(restaurant_a.pk)

    assert [b.pk for b in result] == [wanted.pk]


@pytest.mark.django_db
def test_update_persists_only_the_given_fields():
    branch = BranchFactory(name="Old Name", capacity=10)

    updated = BranchRepository().update(branch, name="New Name")

    branch.refresh_from_db()
    assert updated.name == "New Name"
    assert branch.capacity == 10


@pytest.mark.django_db
def test_delete_removes_the_row():
    branch = BranchFactory()
    branch_id = branch.pk

    BranchRepository().delete(branch)

    assert BranchRepository().get_by_id(branch_id) is None
