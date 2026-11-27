from datetime import datetime, time, timezone

from apps.branches.domain.opening_hours import ClosureWindow, HoursWindow, is_open_at

MONDAY = datetime(2026, 11, 23, tzinfo=timezone.utc)  # a known Monday
TUESDAY = datetime(2026, 11, 24, tzinfo=timezone.utc)

HOURS = [HoursWindow(weekday=0, opens_at=time(9, 0), closes_at=time(22, 0))]


def test_open_within_the_weekly_window():
    at = MONDAY.replace(hour=12)
    assert is_open_at(is_active=True, hours=HOURS, closures=[], at=at) is True


def test_open_exactly_at_the_opening_minute():
    at = MONDAY.replace(hour=9, minute=0)
    assert is_open_at(is_active=True, hours=HOURS, closures=[], at=at) is True


def test_open_exactly_at_the_closing_minute():
    at = MONDAY.replace(hour=22, minute=0)
    assert is_open_at(is_active=True, hours=HOURS, closures=[], at=at) is True


def test_closed_one_minute_before_opening():
    at = MONDAY.replace(hour=8, minute=59)
    assert is_open_at(is_active=True, hours=HOURS, closures=[], at=at) is False


def test_closed_one_minute_after_closing():
    at = MONDAY.replace(hour=22, minute=1)
    assert is_open_at(is_active=True, hours=HOURS, closures=[], at=at) is False


def test_closed_on_a_weekday_with_no_hours_row():
    at = TUESDAY.replace(hour=12)
    assert is_open_at(is_active=True, hours=HOURS, closures=[], at=at) is False


def test_closed_when_branch_is_inactive_even_during_normal_hours():
    at = MONDAY.replace(hour=12)
    assert is_open_at(is_active=False, hours=HOURS, closures=[], at=at) is False


def test_closed_during_a_closure_starting_mid_day_even_though_hours_say_open():
    closure = ClosureWindow(
        starts_at=MONDAY.replace(hour=14, minute=0), ends_at=MONDAY.replace(hour=18, minute=0)
    )
    at = MONDAY.replace(hour=15, minute=0)
    assert is_open_at(is_active=True, hours=HOURS, closures=[closure], at=at) is False


def test_open_outside_a_closures_window_on_the_same_day():
    closure = ClosureWindow(
        starts_at=MONDAY.replace(hour=14, minute=0), ends_at=MONDAY.replace(hour=18, minute=0)
    )
    at = MONDAY.replace(hour=10, minute=0)
    assert is_open_at(is_active=True, hours=HOURS, closures=[closure], at=at) is True


def test_closed_exactly_at_a_closures_start_instant():
    closure = ClosureWindow(
        starts_at=MONDAY.replace(hour=14, minute=0), ends_at=MONDAY.replace(hour=18, minute=0)
    )
    assert (
        is_open_at(is_active=True, hours=HOURS, closures=[closure], at=closure.starts_at) is False
    )
