from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# Lunch (12-14) and dinner (18-21) rush hours get much more weight than the rest of
# the day; weights are relative, not percentages, and index == hour-of-day (0-23).
HOUR_WEIGHTS = [
    1, 1, 1, 1, 1, 1,  # 00-05: closed/overnight
    2, 3, 4, 5,  # 06-09: opening ramp-up
    6, 8,  # 10-11
    14, 16, 10,  # 12-14: lunch rush
    6, 6, 7,  # 15-17
    15, 18, 16, 10,  # 18-21: dinner rush
    5, 3,  # 22-23
]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def random_order_timestamp(rng: random.Random, window_start: datetime, window_end: datetime) -> datetime:
    """A day uniformly within the window, but an hour-of-day weighted toward rush hours.

    Falls back to a plain uniform offset (no hour-of-day weighting) for windows
    narrower than a day, where the rush-hour model doesn't have room to apply.
    """
    window_seconds = int((window_end - window_start).total_seconds())
    if window_seconds <= 0:
        return window_start

    window_days = max(window_seconds // 86_400, 1)
    for _ in range(100):
        day_offset = rng.randrange(window_days)
        hour = rng.choices(range(24), weights=HOUR_WEIGHTS, k=1)[0]
        minute = rng.randrange(60)
        second = rng.randrange(60)
        candidate = window_start + timedelta(
            days=day_offset, hours=hour, minutes=minute, seconds=second
        )
        if candidate <= window_end:
            return candidate

    return window_start + timedelta(seconds=rng.randrange(window_seconds))
