from datetime import time, timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.branches.models import Branch, BranchClosure, BusinessHours


class BranchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Branch

    # String-form SubFactory (factory_boy's own lazy-import mechanism) -- avoids a top-level
    # `from apps.restaurants.tests.factories import RestaurantFactory` in this module, the
    # same reasoning as `Branch.restaurant`'s lazy string FK (ADR 0004; see models/branch.py).
    restaurant = factory.SubFactory("apps.restaurants.tests.factories.RestaurantFactory")
    name = factory.Sequence(lambda n: f"Branch {n}")
    address = "123 Main St"
    latitude = Decimal("40.730610")
    longitude = Decimal("-73.935242")
    phone = "+10000000000"
    delivery_radius_km = Decimal("5.00")
    delivery_fee = Decimal("2.50")
    minimum_order_amount = Decimal("10.00")
    average_prep_time_minutes = 20
    capacity = 50
    is_active = True


class BusinessHoursFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BusinessHours

    branch = factory.SubFactory(BranchFactory)
    weekday = 0
    opens_at = time(9, 0)
    closes_at = time(22, 0)


class BranchClosureFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BranchClosure

    branch = factory.SubFactory(BranchFactory)
    starts_at = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    ends_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))
    reason = "Holiday"
