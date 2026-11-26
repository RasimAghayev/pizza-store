from __future__ import annotations

from typing import Any

from .config import Context

# Arbitrary, plausible single-city bounding box -- purely cosmetic since this data
# is fully synthetic and not meant to resolve to any real place.
LAT_RANGE = (40.30, 40.50)
LON_RANGE = (49.70, 49.95)

OPEN_HOUR = 10
CLOSE_HOUR = 23


def generate_branches(ctx: Context) -> list[dict[str, Any]]:
    branches: list[dict[str, Any]] = []
    for branch_id in range(1, ctx.config.branch_count + 1):
        rng = ctx.random
        branches.append(
            {
                "branch_id": branch_id,
                "name": f"{ctx.faker.city()} #{branch_id}",
                "address": ctx.faker.street_address(),
                "latitude": round(rng.uniform(*LAT_RANGE), 6),
                "longitude": round(rng.uniform(*LON_RANGE), 6),
                "opens_at": f"{OPEN_HOUR:02d}:00",
                "closes_at": f"{CLOSE_HOUR:02d}:00",
                "delivery_radius_km": rng.choice([3, 4, 5, 6, 8]),
                "delivery_fee_minor": rng.choice([300, 400, 500, 600]),
            }
        )
    return branches
