from datetime import datetime, time, timezone
from decimal import Decimal

import pytest

from apps.branches.services.branch_service import BranchNotFoundError, BranchService
from apps.branches.tests.factories import BranchClosureFactory, BranchFactory, BusinessHoursFactory
from apps.restaurants.services.restaurant_service import RestaurantNotFoundError
from apps.restaurants.tests.factories import RestaurantFactory

MONDAY_NOON = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
MONDAY_EARLY_MORNING = datetime(2026, 11, 23, 7, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_create_raises_when_the_restaurant_does_not_exist():
    with pytest.raises(RestaurantNotFoundError):
        BranchService().create(
            restaurant_id=999_999,
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


@pytest.mark.django_db
def test_create_persists_a_branch_for_an_existing_restaurant():
    restaurant = RestaurantFactory()

    branch = BranchService().create(
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
def test_organization_id_for_restaurant_returns_the_owning_organization():
    restaurant = RestaurantFactory()

    organization_id = BranchService().organization_id_for_restaurant(restaurant.pk)

    assert organization_id == restaurant.organization_id


@pytest.mark.django_db
def test_organization_id_for_restaurant_is_none_for_an_unknown_restaurant():
    assert BranchService().organization_id_for_restaurant(999_999) is None


@pytest.mark.django_db
def test_update_raises_when_the_branch_does_not_exist():
    with pytest.raises(BranchNotFoundError):
        BranchService().update(999_999, name="New Name")


@pytest.mark.django_db
def test_is_open_now_is_false_outside_business_hours():
    branch = BranchFactory()
    BusinessHoursFactory(branch=branch, weekday=0, opens_at=time(9, 0), closes_at=time(22, 0))

    assert BranchService().is_open_now(branch.pk, at=MONDAY_EARLY_MORNING) is False


@pytest.mark.django_db
def test_is_open_now_is_true_within_business_hours_with_no_active_closure():
    branch = BranchFactory()
    BusinessHoursFactory(branch=branch, weekday=0, opens_at=time(9, 0), closes_at=time(22, 0))

    assert BranchService().is_open_now(branch.pk, at=MONDAY_NOON) is True


@pytest.mark.django_db
def test_is_open_now_is_false_during_an_active_closure():
    branch = BranchFactory()
    BusinessHoursFactory(branch=branch, weekday=0, opens_at=time(9, 0), closes_at=time(22, 0))
    BranchClosureFactory(
        branch=branch,
        starts_at=MONDAY_NOON.replace(hour=10),
        ends_at=MONDAY_NOON.replace(hour=15),
    )

    assert BranchService().is_open_now(branch.pk, at=MONDAY_NOON) is False


@pytest.mark.django_db
def test_within_delivery_radius_of_matches_a_nearby_branch_and_excludes_a_far_one():
    near = BranchFactory(
        latitude=Decimal("40.730610"),
        longitude=Decimal("-73.935242"),
        delivery_radius_km=Decimal("5.00"),
    )
    BranchFactory(
        latitude=Decimal("34.052235"),
        longitude=Decimal("-118.243683"),
        delivery_radius_km=Decimal("5.00"),
    )

    matches = BranchService().within_delivery_radius_of(
        latitude=Decimal("40.730610"), longitude=Decimal("-73.935242")
    )

    matched_ids = {branch.pk for branch in matches}
    assert near.pk in matched_ids
    assert len(matches) == 1
