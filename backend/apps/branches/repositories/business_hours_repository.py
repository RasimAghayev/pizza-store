from datetime import time

from apps.branches.models import BusinessHours


class BusinessHoursRepository:
    """Only file in this module allowed to issue an ORM query for BusinessHours, per ADR 0004."""

    def set_hours(
        self, *, branch_id: int, weekday: int, opens_at: time, closes_at: time
    ) -> BusinessHours:
        row, _ = BusinessHours.objects.update_or_create(
            branch_id=branch_id,
            weekday=weekday,
            defaults={"opens_at": opens_at, "closes_at": closes_at},
        )
        return row

    def clear_day(self, *, branch_id: int, weekday: int) -> None:
        BusinessHours.objects.filter(branch_id=branch_id, weekday=weekday).delete()

    def for_branch(self, branch_id: int) -> list[BusinessHours]:
        return list(BusinessHours.objects.filter(branch_id=branch_id).order_by("weekday"))
