from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class HoursWindow:
    weekday: int
    opens_at: time
    closes_at: time


@dataclass(frozen=True)
class ClosureWindow:
    starts_at: datetime
    ends_at: datetime


def is_open_at(
    *,
    is_active: bool,
    hours: Iterable[HoursWindow],
    closures: Iterable[ClosureWindow],
    at: datetime,
) -> bool:
    """Pure domain logic (ADR 0004: no Django/ORM imports) -- called by
    `branches/services/branch_service.py::BranchService.is_open_now` with the real model rows
    translated into these dataclasses by the repository layer. Order matters: an inactive
    branch or an active closure always wins over the weekly schedule, regardless of what
    `hours` says for `at`'s weekday. Boundaries are inclusive on both ends (a branch counts as
    open exactly at its opening minute and exactly at its closing minute, and a closure covers
    its own `starts_at`/`ends_at` instant). Does not handle a window that spans midnight
    (`closes_at` <= `opens_at`) -- no current branch needs one; `BusinessHours` would need a
    second row for the overflow day if that ever changes."""
    if not is_active:
        return False

    if any(closure.starts_at <= at <= closure.ends_at for closure in closures):
        return False

    weekday = at.weekday()
    local_time = at.time()
    return any(
        window.weekday == weekday and window.opens_at <= local_time <= window.closes_at
        for window in hours
    )
