from decimal import Decimal

from django.db.models import ExpressionWrapper, F, FloatField, Value
from django.db.models.functions import ACos, Cast, Cos, Greatest, Least, Radians, Sin

from apps.branches.models import Branch

EARTH_RADIUS_KM = 6371.0


class BranchRepository:
    """Only file in this module allowed to issue an ORM query for Branch, per ADR 0004.
    Takes `restaurant_id`, never a `restaurants.Restaurant` instance -- `Branch.restaurant` is
    a lazy string FK (`models.ForeignKey("restaurants.Restaurant", ...)`, see
    `models/branch.py`) specifically so this module never imports `apps.restaurants.models`;
    assigning `restaurant_id=` directly resolves the FK column without needing the related
    object or its class."""

    def create(
        self,
        *,
        restaurant_id: int,
        name: str,
        address: str,
        latitude: Decimal,
        longitude: Decimal,
        phone: str,
        delivery_radius_km: Decimal,
        delivery_fee: Decimal,
        minimum_order_amount: Decimal,
        average_prep_time_minutes: int,
        capacity: int,
        is_active: bool = True,
    ) -> Branch:
        return Branch.objects.create(
            restaurant_id=restaurant_id,
            name=name,
            address=address,
            latitude=latitude,
            longitude=longitude,
            phone=phone,
            delivery_radius_km=delivery_radius_km,
            delivery_fee=delivery_fee,
            minimum_order_amount=minimum_order_amount,
            average_prep_time_minutes=average_prep_time_minutes,
            capacity=capacity,
            is_active=is_active,
        )

    def get_by_id(self, branch_id: int) -> Branch | None:
        return Branch.objects.filter(pk=branch_id).first()

    def all(self) -> list[Branch]:
        return list(Branch.objects.order_by("name"))

    def filter_by_restaurant(self, restaurant_id: int) -> list[Branch]:
        return list(Branch.objects.filter(restaurant_id=restaurant_id).order_by("name"))

    def update(self, branch: Branch, **fields: object) -> Branch:
        for field, value in fields.items():
            setattr(branch, field, value)
        branch.save(update_fields=list(fields))
        return branch

    def delete(self, branch: Branch) -> None:
        branch.delete()

    def within_delivery_radius_of(self, *, latitude: Decimal, longitude: Decimal) -> list[Branch]:
        """Haversine distance computed in SQL via plain Postgres math functions (no PostGIS
        installed) so filtering scales with a `WHERE`, not a full-table fetch into Python.
        Matches each branch against its *own* `delivery_radius_km` -- "find branches that
        would deliver to this point" -- not a caller-supplied radius, per Issue #180's
        Implementation Prompt. `Greatest`/`Least` clamp the cosine to `[-1, 1]` because a
        point's distance from itself can compute as e.g. `1.0000000000000002` under
        floating-point rounding, which `ACos` would otherwise reject as out of domain."""
        point_lat = Radians(Value(float(latitude), output_field=FloatField()))
        point_lon = Radians(Value(float(longitude), output_field=FloatField()))
        branch_lat = Radians(Cast(F("latitude"), output_field=FloatField()))
        branch_lon = Radians(Cast(F("longitude"), output_field=FloatField()))

        cos_angle = Greatest(
            Least(
                Cos(point_lat) * Cos(branch_lat) * Cos(branch_lon - point_lon)
                + Sin(point_lat) * Sin(branch_lat),
                Value(1.0, output_field=FloatField()),
            ),
            Value(-1.0, output_field=FloatField()),
        )
        distance_km = ExpressionWrapper(
            Value(EARTH_RADIUS_KM, output_field=FloatField()) * ACos(cos_angle),
            output_field=FloatField(),
        )

        return list(
            Branch.objects.filter(is_active=True)
            .annotate(distance_km=distance_km)
            .filter(distance_km__lte=Cast(F("delivery_radius_km"), output_field=FloatField()))
            .order_by("distance_km")
        )
