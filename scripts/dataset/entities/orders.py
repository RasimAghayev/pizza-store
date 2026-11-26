from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from .campaigns import active_general_campaigns
from .config import Context
from .timeutil import iso, random_order_timestamp

NORMAL_STEPS: list[tuple[str, tuple[int, int]]] = [
    ("DRAFT_CART", (0, 0)),
    ("PENDING_PAYMENT", (1, 5)),
    ("CONFIRMED", (1, 3)),
    ("ACCEPTED", (1, 5)),
    ("PREPARING", (1, 5)),
    ("BAKING", (5, 12)),
    ("READY", (5, 10)),
    ("COURIER_ASSIGNED", (1, 5)),
    ("PICKED_UP", (2, 8)),
    ("ON_THE_WAY", (1, 3)),
    ("DELIVERED", (8, 20)),
]

# Worst case (refunded: up to ~4d pending + 48h refund) comfortably fits with margin.
SAFETY_BUFFER_DAYS = 8
STALLED_WINDOW_DAYS = 3

OUTCOME_WEIGHTS = {
    "normal": 0.80,
    "late": 0.10,
    "payment_failed": 0.03,
    "cancelled": 0.03,
    "refunded": 0.03,
    "stalled": 0.01,
}

ITEM_COUNT_CHOICES = [1, 2, 3, 4, 5]
ITEM_COUNT_WEIGHTS = [10, 35, 30, 15, 10]
QUANTITY_CHOICES = [1, 2, 3]
QUANTITY_WEIGHTS = [70, 25, 5]

BIRTHDAY_REDEMPTION_WINDOW_DAYS = 7
BIRTHDAY_REDEMPTION_PROBABILITY = 0.5
GENERAL_CAMPAIGN_PROBABILITY = 0.15


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _build_steps(
    rng: Any, created_at: datetime, category: str
) -> list[tuple[str, datetime]]:
    multiplier = 4 if category == "late" else 1
    steps: list[tuple[str, datetime]] = []
    current = created_at

    cancel_cut_index = rng.choice([2, 3, 4]) if category == "cancelled" else None
    stall_cut_index = rng.choice([3, 4, 5, 6]) if category == "stalled" else None

    for index, (status, (low, high)) in enumerate(NORMAL_STEPS):
        if index == 0:
            current = created_at
        else:
            gap_minutes = rng.randint(low, high) * multiplier
            current = current + timedelta(minutes=gap_minutes)
        steps.append((status, current))

        if category == "payment_failed" and status == "PENDING_PAYMENT":
            current = current + timedelta(minutes=rng.randint(1, 10))
            steps.append(("PAYMENT_FAILED", current))
            return steps

        if category == "cancelled" and index == cancel_cut_index:
            current = current + timedelta(minutes=rng.randint(5, 30))
            steps.append(("CANCELLED", current))
            return steps

        if category == "stalled" and index == stall_cut_index:
            return steps

        if status == "DELIVERED":
            if category == "refunded":
                pending_at = current + timedelta(
                    days=rng.randint(1, 4), minutes=rng.randint(0, 59)
                )
                refunded_at = pending_at + timedelta(hours=rng.randint(2, 48))
                steps.append(("REFUND_PENDING", pending_at))
                steps.append(("REFUNDED", refunded_at))
            return steps

    return steps


def _current_address_id(
    addresses_for_customer: list[tuple[datetime, int]], at: datetime
) -> int:
    current = addresses_for_customer[0][1]
    for effective_from, address_id in addresses_for_customer:
        if effective_from <= at:
            current = address_id
        else:
            break
    return current


def generate_orders(
    ctx: Context,
    branches: list[dict[str, Any]],
    products: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    addresses: list[dict[str, Any]],
    couriers: list[dict[str, Any]],
    general_campaigns: list[dict[str, Any]],
    birthday_campaigns: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rng = ctx.random
    window_start, window_end = ctx.config.window_start, ctx.config.window_end
    normal_cutoff = window_end - timedelta(days=SAFETY_BUFFER_DAYS)
    stalled_start = window_end - timedelta(days=STALLED_WINDOW_DAYS)

    branch_ids = [b["branch_id"] for b in branches]
    branch_fee = {b["branch_id"]: b["delivery_fee_minor"] for b in branches}
    pizza_products = [p for p in products if p["category"] == "pizza_variant"]
    non_pizza_products = [p for p in products if p["category"] != "pizza_variant"]
    courier_ids = [c["courier_id"] for c in couriers]

    registered_at_by_customer = {c["customer_id"]: _parse(c["registered_at"]) for c in customers}

    addr_by_customer: dict[int, list[tuple[datetime, int]]] = defaultdict(list)
    for a in addresses:
        addr_by_customer[a["customer_id"]].append((_parse(a["effective_from"]), a["address_id"]))
    for lst in addr_by_customer.values():
        lst.sort()

    bday_by_customer: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for bc in birthday_campaigns:
        bday_by_customer[bc["customer_id"]].append(bc)

    # Repeat-order skew: most customers order once or twice, a minority order often.
    customer_ids = [c["customer_id"] for c in customers]
    propensity = [rng.choice([1, 1, 1, 1, 2, 2, 3, 5, 8]) for _ in customer_ids]
    order_count = ctx.config.order_count
    assigned_customer_ids = rng.choices(customer_ids, weights=propensity, k=order_count)

    orders: list[dict[str, Any]] = []
    order_items: list[dict[str, Any]] = []
    status_history: list[dict[str, Any]] = []

    next_order_item_id = 1
    next_status_id = 1

    for order_id in range(1, order_count + 1):
        customer_id = assigned_customer_ids[order_id - 1]
        registered_at = registered_at_by_customer[customer_id]

        category = rng.choices(
            list(OUTCOME_WEIGHTS), weights=list(OUTCOME_WEIGHTS.values()), k=1
        )[0]
        if category == "stalled":
            earliest = max(stalled_start, registered_at)
            if earliest >= window_end:
                category = "normal"
            else:
                created_at = random_order_timestamp(rng, earliest, window_end)
        if category != "stalled":
            earliest = max(window_start, registered_at)
            latest = max(normal_cutoff, earliest + timedelta(hours=1))
            created_at = random_order_timestamp(rng, earliest, latest)

        branch_id = rng.choice(branch_ids)

        item_count = rng.choices(ITEM_COUNT_CHOICES, weights=ITEM_COUNT_WEIGHTS, k=1)[0]
        items_for_order: list[dict[str, Any]] = []
        subtotal_minor = 0
        for _ in range(item_count):
            pool = pizza_products if rng.random() < 0.6 else non_pizza_products
            product = rng.choice(pool)
            quantity = rng.choices(QUANTITY_CHOICES, weights=QUANTITY_WEIGHTS, k=1)[0]
            line_total = product["base_price_minor"] * quantity
            items_for_order.append(
                {
                    "order_item_id": next_order_item_id,
                    "order_id": order_id,
                    "product_id": product["product_id"],
                    "quantity": quantity,
                    "unit_price_minor": product["base_price_minor"],
                    "line_total_minor": line_total,
                }
            )
            next_order_item_id += 1
            subtotal_minor += line_total

        applied_campaign_type = None
        applied_campaign_id = None
        discount_percent = 0

        candidate_bdays = [
            bc
            for bc in bday_by_customer.get(customer_id, [])
            if not bc["applied"]
            and _parse(bc["triggered_at"]) <= created_at
            <= _parse(bc["triggered_at"]) + timedelta(days=BIRTHDAY_REDEMPTION_WINDOW_DAYS)
        ]
        if candidate_bdays and rng.random() < BIRTHDAY_REDEMPTION_PROBABILITY:
            bc = candidate_bdays[0]
            bc["applied"] = True
            bc["order_id"] = order_id
            applied_campaign_type = "BIRTHDAY"
            applied_campaign_id = bc["birthday_campaign_id"]
            discount_percent = bc["discount_percent"]
        else:
            active = active_general_campaigns(general_campaigns, created_at)
            if active and rng.random() < GENERAL_CAMPAIGN_PROBABILITY:
                campaign = rng.choice(active)
                applied_campaign_type = "GENERAL"
                applied_campaign_id = campaign["campaign_id"]
                discount_percent = campaign["discount_percent"]

        discount_minor = (subtotal_minor * discount_percent) // 100
        delivery_fee_minor = branch_fee[branch_id]
        total_minor = subtotal_minor + delivery_fee_minor - discount_minor

        steps = _build_steps(rng, created_at, category)
        step_statuses = {status for status, _ in steps}

        address_id = _current_address_id(addr_by_customer[customer_id], created_at)
        courier_id = (
            rng.choice(courier_ids) if "COURIER_ASSIGNED" in step_statuses else None
        )

        final_status = steps[-1][0]

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "branch_id": branch_id,
                "address_id": address_id,
                "courier_id": courier_id,
                "created_at": iso(created_at),
                "final_status": final_status,
                "subtotal_minor": subtotal_minor,
                "delivery_fee_minor": delivery_fee_minor,
                "discount_minor": discount_minor,
                "total_minor": total_minor,
                "applied_campaign_type": applied_campaign_type,
                "applied_campaign_id": applied_campaign_id,
            }
        )
        order_items.extend(items_for_order)
        for status, occurred_at in steps:
            status_history.append(
                {
                    "status_history_id": next_status_id,
                    "order_id": order_id,
                    "status": status,
                    "occurred_at": iso(occurred_at),
                }
            )
            next_status_id += 1

    return orders, order_items, status_history
