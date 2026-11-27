from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from .config import Context
from .timeutil import iso

GENERAL_CAMPAIGN_COUNT = 16
GENERAL_CAMPAIGN_NAMES = [
    "WELCOME5",
    "SUMMER10",
    "WINTER15",
    "FLASH20",
    "WEEKEND10",
    "FAMILYPACK",
    "STUDENT10",
    "FIRSTORDER",
    "LOYALTY5",
    "REFERRAL10",
    "APP15",
    "LUNCHDEAL",
    "DINNERDEAL",
    "HOLIDAY20",
    "COMEBACK10",
    "BUNDLE15",
]

BIRTHDAY_ELIGIBILITY_RATE = 0.15
BIRTHDAY_DISCOUNT_PERCENT = 20


def generate_general_campaigns(ctx: Context) -> list[dict[str, Any]]:
    campaigns: list[dict[str, Any]] = []
    window_days = ctx.config.window_days
    for campaign_id, name in enumerate(GENERAL_CAMPAIGN_NAMES[:GENERAL_CAMPAIGN_COUNT], start=1):
        start_offset = ctx.random.randrange(window_days - 30)
        duration_days = ctx.random.randrange(14, 60)
        valid_from = ctx.config.window_start + timedelta(days=start_offset)
        valid_to = valid_from + timedelta(days=duration_days)
        campaigns.append(
            {
                "campaign_id": campaign_id,
                "name": name,
                "discount_percent": ctx.random.choice([5, 10, 15, 20]),
                "valid_from": iso(valid_from),
                "valid_to": iso(valid_to),
            }
        )
    return campaigns


def active_general_campaigns(
    campaigns: list[dict[str, Any]], at: datetime
) -> list[dict[str, Any]]:
    return [
        c
        for c in campaigns
        if datetime.fromisoformat(c["valid_from"].replace("Z", "+00:00")) <= at
        and at <= datetime.fromisoformat(c["valid_to"].replace("Z", "+00:00"))
    ]


def generate_birthday_campaigns(
    ctx: Context, customers: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """One record per (eligible customer, birthday-occurrence-within-window). Mutated
    in place by orders.py when a real order redeems it: sets applied/order_id so the
    same occurrence can never be redeemed twice."""
    redemption_id = 1
    birthday_campaigns: list[dict[str, Any]] = []
    window_start, window_end = ctx.config.window_start, ctx.config.window_end

    for customer in customers:
        if ctx.random.random() >= BIRTHDAY_ELIGIBILITY_RATE:
            continue
        registered_at = datetime.fromisoformat(customer["registered_at"].replace("Z", "+00:00"))
        for year in range(window_start.year, window_end.year + 1):
            try:
                occurrence = date(year, customer["birth_month"], customer["birth_day"])
            except ValueError:
                continue
            occurrence_dt = datetime(
                occurrence.year, occurrence.month, occurrence.day, tzinfo=timezone.utc
            )
            earliest = max(window_start, registered_at)
            if not (earliest <= occurrence_dt <= window_end):
                continue
            birthday_campaigns.append(
                {
                    "birthday_campaign_id": redemption_id,
                    "customer_id": customer["customer_id"],
                    "discount_percent": BIRTHDAY_DISCOUNT_PERCENT,
                    "triggered_at": iso(occurrence_dt),
                    "applied": False,
                    "order_id": None,
                }
            )
            redemption_id += 1

    return birthday_campaigns
