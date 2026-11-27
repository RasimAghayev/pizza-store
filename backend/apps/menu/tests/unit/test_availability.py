from datetime import time

from apps.menu.domain.availability import is_available_at


def test_unavailable_item_is_excluded_regardless_of_window():
    assert not is_available_at(
        is_available=False,
        available_from=time(11, 0),
        available_until=time(14, 0),
        at=time(12, 0),
    )


def test_no_window_means_always_available():
    assert is_available_at(
        is_available=True, available_from=None, available_until=None, at=time(3, 0)
    )


def test_exactly_at_available_from_is_included():
    assert is_available_at(
        is_available=True,
        available_from=time(11, 0),
        available_until=time(14, 0),
        at=time(11, 0),
    )


def test_just_before_available_from_is_excluded():
    assert not is_available_at(
        is_available=True,
        available_from=time(11, 0),
        available_until=time(14, 0),
        at=time(10, 59, 59),
    )


def test_inside_the_window_is_included():
    assert is_available_at(
        is_available=True,
        available_from=time(11, 0),
        available_until=time(14, 0),
        at=time(12, 30),
    )


def test_exactly_at_available_until_is_excluded():
    assert not is_available_at(
        is_available=True,
        available_from=time(11, 0),
        available_until=time(14, 0),
        at=time(14, 0),
    )


def test_just_after_available_until_is_excluded():
    assert not is_available_at(
        is_available=True,
        available_from=time(11, 0),
        available_until=time(14, 0),
        at=time(14, 0, 1),
    )
