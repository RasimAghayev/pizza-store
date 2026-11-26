from __future__ import annotations

from datetime import timedelta
from typing import Any

from .config import Context
from .timeutil import iso

STAFF_ROLES = [
    "CASHIER",
    "KITCHEN_STAFF",
    "KITCHEN_MANAGER",
    "BRANCH_MANAGER",
    "INVENTORY_MANAGER",
]
VEHICLE_TYPES = ["BIKE", "SCOOTER", "CAR"]
EMAIL_DOMAINS = ["example.com", "example.net", "example.org"]


def _email(ctx: Context, first: str, last: str, unique_id: int) -> str:
    domain = ctx.random.choice(EMAIL_DOMAINS)
    return f"{first.lower()}.{last.lower()}{unique_id}@{domain}".replace(" ", "")


def _phone(ctx: Context) -> str:
    return f"+1{ctx.random.randrange(2000000000, 9999999999)}"


def generate_staff(ctx: Context, branch_ids: list[int]) -> list[dict[str, Any]]:
    staff: list[dict[str, Any]] = []
    for staff_id in range(1, ctx.config.staff_count + 1):
        first, last = ctx.faker.first_name(), ctx.faker.last_name()
        hired_at = ctx.config.window_start + timedelta(
            days=ctx.random.randrange(ctx.config.window_days)
        )
        staff.append(
            {
                "staff_id": staff_id,
                "branch_id": ctx.random.choice(branch_ids),
                "first_name": first,
                "last_name": last,
                "email": _email(ctx, first, last, staff_id),
                "phone": _phone(ctx),
                "role": ctx.random.choice(STAFF_ROLES),
                "hired_at": iso(hired_at),
                "is_active": True,
            }
        )
    return staff


def generate_couriers(ctx: Context, branch_ids: list[int]) -> list[dict[str, Any]]:
    couriers: list[dict[str, Any]] = []
    for courier_id in range(1, ctx.config.courier_count + 1):
        first, last = ctx.faker.first_name(), ctx.faker.last_name()
        hired_at = ctx.config.window_start + timedelta(
            days=ctx.random.randrange(ctx.config.window_days)
        )
        couriers.append(
            {
                "courier_id": courier_id,
                "branch_id": ctx.random.choice(branch_ids),
                "first_name": first,
                "last_name": last,
                "email": _email(ctx, first, last, 100_000 + courier_id),
                "phone": _phone(ctx),
                "vehicle_type": ctx.random.choice(VEHICLE_TYPES),
                "hired_at": iso(hired_at),
                "is_active": True,
            }
        )
    return couriers


def generate_customers(
    ctx: Context,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (customers, customer_addresses). Each customer gets 1-3 addresses
    across the window so the address-change scenario (Task #18) has real history to
    draw from; `is_current` marks the address orders should use after its effective date.
    """
    customers: list[dict[str, Any]] = []
    addresses: list[dict[str, Any]] = []
    address_id = 1

    for customer_id in range(1, ctx.config.customer_count + 1):
        first, last = ctx.faker.first_name(), ctx.faker.last_name()
        registered_at = ctx.config.window_start + timedelta(
            days=ctx.random.randrange(ctx.config.window_days)
        )
        birth_year = ctx.random.randint(1955, 2008)
        birth_month = ctx.random.randint(1, 12)
        birth_day = ctx.random.randint(1, 28)

        customers.append(
            {
                "customer_id": customer_id,
                "first_name": first,
                "last_name": last,
                "email": _email(ctx, first, last, customer_id),
                "phone": _phone(ctx),
                "birth_month": birth_month,
                "birth_day": birth_day,
                "birth_year": birth_year,
                "registered_at": iso(registered_at),
                "loyalty_points_balance": 0,
            }
        )

        # ~20% of customers change their saved address at least once during the window.
        days_available = max((ctx.config.window_end - registered_at).days, 0)
        address_change_count = 1
        if ctx.random.random() < 0.20 and days_available > 2:
            address_change_count = min(ctx.random.choice([2, 3]), days_available)

        change_offsets: list[int] = []
        if address_change_count > 1:
            change_offsets = sorted(
                ctx.random.sample(range(1, days_available), k=address_change_count - 1)
            )
        effective_from_offsets = [0, *change_offsets]

        for index, offset in enumerate(effective_from_offsets):
            effective_from = registered_at + timedelta(days=offset)
            addresses.append(
                {
                    "address_id": address_id,
                    "customer_id": customer_id,
                    "line1": ctx.faker.street_address(),
                    "city": ctx.faker.city(),
                    "effective_from": iso(effective_from),
                    "is_current": index == len(effective_from_offsets) - 1,
                }
            )
            address_id += 1

    return customers, addresses
