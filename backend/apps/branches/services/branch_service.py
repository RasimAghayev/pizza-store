from datetime import datetime, time
from decimal import Decimal

from django.utils import timezone

from apps.branches.domain.opening_hours import ClosureWindow, HoursWindow, is_open_at
from apps.branches.models import Branch, BranchClosure, BusinessHours
from apps.branches.repositories.branch_closure_repository import BranchClosureRepository
from apps.branches.repositories.branch_repository import BranchRepository
from apps.branches.repositories.business_hours_repository import BusinessHoursRepository

# calls apps.restaurants.services.restaurant_service.RestaurantService.get_by_id() -- see
# backend/apps/restaurants/README.md. branches never imports apps.restaurants.models/
# repositories directly (ADR 0004); Branch.restaurant is a lazy string FK for the same reason.
from apps.restaurants.services.restaurant_service import RestaurantNotFoundError, RestaurantService


class BranchNotFoundError(Exception):
    pass


class ClosureNotFoundError(Exception):
    pass


class BranchService:
    def __init__(
        self,
        repository: BranchRepository | None = None,
        hours_repository: BusinessHoursRepository | None = None,
        closure_repository: BranchClosureRepository | None = None,
        restaurant_service: RestaurantService | None = None,
    ) -> None:
        self._repository = repository or BranchRepository()
        self._hours_repository = hours_repository or BusinessHoursRepository()
        self._closure_repository = closure_repository or BranchClosureRepository()
        self._restaurant_service = restaurant_service or RestaurantService()

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
        if self._restaurant_service.get_by_id(restaurant_id) is None:
            raise RestaurantNotFoundError(restaurant_id)
        return self._repository.create(
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
        return self._repository.get_by_id(branch_id)

    def list_all(self) -> list[Branch]:
        """Unfiltered -- the public, AllowAny read path (menu-browsing needs this before
        login exists, Issue #180's Implementation Prompt)."""
        return self._repository.all()

    def within_delivery_radius_of(self, *, latitude: Decimal, longitude: Decimal) -> list[Branch]:
        return self._repository.within_delivery_radius_of(latitude=latitude, longitude=longitude)

    def update(self, branch_id: int, **fields: object) -> Branch:
        branch = self._repository.get_by_id(branch_id)
        if branch is None:
            raise BranchNotFoundError(branch_id)
        return self._repository.update(branch, **fields)

    def delete(self, branch_id: int) -> None:
        branch = self._repository.get_by_id(branch_id)
        if branch is None:
            raise BranchNotFoundError(branch_id)
        self._repository.delete(branch)

    def organization_id_for_restaurant(self, restaurant_id: int) -> int | None:
        """`TwoStepPermission`'s scope hook for Branch needs the owning organization's id,
        which Branch itself does not store -- re-derived through `RestaurantService`
        (the sanctioned cross-module read, see this class's docstring) rather than Branch
        gaining a denormalized `organization_id` column. Takes `restaurant_id` directly
        (not a `Branch` instance) so the same lookup serves an existing Branch
        (`branch.restaurant_id`) and a not-yet-saved create payload alike."""
        restaurant = self._restaurant_service.get_by_id(restaurant_id)
        return restaurant.organization_id if restaurant is not None else None

    def set_hours(
        self, *, branch_id: int, weekday: int, opens_at: time, closes_at: time
    ) -> BusinessHours:
        if self._repository.get_by_id(branch_id) is None:
            raise BranchNotFoundError(branch_id)
        return self._hours_repository.set_hours(
            branch_id=branch_id, weekday=weekday, opens_at=opens_at, closes_at=closes_at
        )

    def hours_for(self, branch_id: int) -> list[BusinessHours]:
        return self._hours_repository.for_branch(branch_id)

    def add_closure(
        self, *, branch_id: int, starts_at: datetime, ends_at: datetime, reason: str = ""
    ) -> BranchClosure:
        if self._repository.get_by_id(branch_id) is None:
            raise BranchNotFoundError(branch_id)
        return self._closure_repository.create(
            branch_id=branch_id, starts_at=starts_at, ends_at=ends_at, reason=reason
        )

    def closures_for(self, branch_id: int) -> list[BranchClosure]:
        return self._closure_repository.for_branch(branch_id)

    def delete_closure(self, closure_id: int) -> None:
        closure = self._closure_repository.get_by_id(closure_id)
        if closure is None:
            raise ClosureNotFoundError(closure_id)
        self._closure_repository.delete(closure)

    def is_open_now(self, branch_id: int, *, at: datetime | None = None) -> bool:
        branch = self._repository.get_by_id(branch_id)
        if branch is None:
            raise BranchNotFoundError(branch_id)
        moment = at or timezone.now()
        hours = [
            HoursWindow(weekday=h.weekday, opens_at=h.opens_at, closes_at=h.closes_at)
            for h in self._hours_repository.for_branch(branch_id)
        ]
        closures = [
            ClosureWindow(starts_at=c.starts_at, ends_at=c.ends_at)
            for c in self._closure_repository.for_branch(branch_id)
        ]
        return is_open_at(is_active=branch.is_active, hours=hours, closures=closures, at=moment)
