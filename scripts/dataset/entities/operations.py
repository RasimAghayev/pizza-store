from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from .branches import LAT_RANGE, LON_RANGE
from .config import Context
from .timeutil import iso

POINTS_PER_MINOR_UNIT = 100  # 1 loyalty point per 100 minor units spent
REDEMPTION_PROBABILITY = 0.08
REVIEW_RATE = 0.25
RATING_CHOICES = [1, 2, 3, 4, 5]
RATING_WEIGHTS = [3, 5, 10, 30, 52]
AUDITABLE_STATUSES = {"CANCELLED", "REFUNDED", "PAYMENT_FAILED"}
RESTOCK_INTERVAL_DAYS = 30


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def generate_loyalty_transactions(
    ctx: Context,
    orders: list[dict[str, Any]],
    status_history: list[dict[str, Any]],
    customers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rng = ctx.random
    delivered_at_by_order: dict[int, str] = {
        e["order_id"]: e["occurred_at"] for e in status_history if e["status"] == "DELIVERED"
    }
    balance_by_customer = {c["customer_id"]: 0 for c in customers}

    transactions: list[dict[str, Any]] = []
    txn_id = 1

    for order in sorted(orders, key=lambda o: o["created_at"]):
        delivered_at = delivered_at_by_order.get(order["order_id"])
        if delivered_at is None:
            continue
        customer_id = order["customer_id"]

        earned = order["total_minor"] // POINTS_PER_MINOR_UNIT
        if earned > 0:
            balance_by_customer[customer_id] += earned
            transactions.append(
                {
                    "loyalty_transaction_id": txn_id,
                    "customer_id": customer_id,
                    "order_id": order["order_id"],
                    "type": "EARN",
                    "points": earned,
                    "occurred_at": delivered_at,
                }
            )
            txn_id += 1

        balance = balance_by_customer[customer_id]
        if balance > 200 and rng.random() < REDEMPTION_PROBABILITY:
            redeemed = rng.randint(100, min(500, balance))
            balance_by_customer[customer_id] -= redeemed
            transactions.append(
                {
                    "loyalty_transaction_id": txn_id,
                    "customer_id": customer_id,
                    "order_id": order["order_id"],
                    "type": "REDEEM",
                    "points": -redeemed,
                    "occurred_at": delivered_at,
                }
            )
            txn_id += 1

    for customer in customers:
        customer["loyalty_points_balance"] = balance_by_customer[customer["customer_id"]]

    return transactions


def generate_inventory_movements(
    ctx: Context,
    branches: list[dict[str, Any]],
    products: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    order_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rng = ctx.random
    branch_by_order = {o["order_id"]: o["branch_id"] for o in orders}
    created_at_by_order = {o["order_id"]: o["created_at"] for o in orders}

    movements: list[dict[str, Any]] = []
    movement_id = 1

    for item in order_items:
        branch_id = branch_by_order.get(item["order_id"])
        if branch_id is None:
            continue
        movements.append(
            {
                "inventory_movement_id": movement_id,
                "branch_id": branch_id,
                "product_id": item["product_id"],
                "type": "SALE",
                "quantity": -item["quantity"],
                "occurred_at": created_at_by_order[item["order_id"]],
            }
        )
        movement_id += 1

    window_start, window_end = ctx.config.window_start, ctx.config.window_end
    restock_count = ctx.config.window_days // RESTOCK_INTERVAL_DAYS
    for branch in branches:
        for product in products:
            for cycle in range(restock_count):
                occurred_at = window_start + timedelta(
                    days=cycle * RESTOCK_INTERVAL_DAYS + rng.randint(0, 5)
                )
                movements.append(
                    {
                        "inventory_movement_id": movement_id,
                        "branch_id": branch["branch_id"],
                        "product_id": product["product_id"],
                        "type": "RESTOCK",
                        "quantity": rng.randint(50, 300),
                        "occurred_at": iso(occurred_at),
                    }
                )
                movement_id += 1

    return movements


def generate_delivery_tracking(
    ctx: Context, branches: list[dict[str, Any]], orders: list[dict[str, Any]], status_history: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rng = ctx.random
    branch_by_id = {b["branch_id"]: b for b in branches}

    window_by_order: dict[int, dict[str, str]] = defaultdict(dict)
    for entry in status_history:
        window_by_order[entry["order_id"]][entry["status"]] = entry["occurred_at"]

    tracking: list[dict[str, Any]] = []
    point_id = 1

    for order in orders:
        statuses_at = window_by_order.get(order["order_id"], {})
        if "PICKED_UP" not in statuses_at:
            continue
        start_at = _parse(statuses_at["PICKED_UP"])
        end_at = _parse(
            statuses_at.get("DELIVERED")
            or statuses_at.get("ON_THE_WAY")
            or statuses_at["PICKED_UP"]
        )
        branch = branch_by_id[order["branch_id"]]
        waypoint_count = rng.randint(3, 6)
        dest_lat = branch["latitude"] + rng.uniform(-0.05, 0.05)
        dest_lon = branch["longitude"] + rng.uniform(-0.05, 0.05)
        total_seconds = max((end_at - start_at).total_seconds(), waypoint_count)

        for step in range(waypoint_count):
            fraction = step / max(waypoint_count - 1, 1)
            occurred_at = start_at + timedelta(seconds=total_seconds * fraction)
            tracking.append(
                {
                    "delivery_tracking_id": point_id,
                    "order_id": order["order_id"],
                    "courier_id": order["courier_id"],
                    "latitude": round(branch["latitude"] + (dest_lat - branch["latitude"]) * fraction, 6),
                    "longitude": round(branch["longitude"] + (dest_lon - branch["longitude"]) * fraction, 6),
                    "occurred_at": iso(occurred_at),
                }
            )
            point_id += 1

    return tracking


def generate_reviews(
    ctx: Context, orders: list[dict[str, Any]], status_history: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rng = ctx.random
    delivered_at_by_order = {
        e["order_id"]: _parse(e["occurred_at"]) for e in status_history if e["status"] == "DELIVERED"
    }

    reviews: list[dict[str, Any]] = []
    review_id = 1
    for order in orders:
        delivered_at = delivered_at_by_order.get(order["order_id"])
        if delivered_at is None or rng.random() >= REVIEW_RATE:
            continue
        rating = rng.choices(RATING_CHOICES, weights=RATING_WEIGHTS, k=1)[0]
        reviewed_at = delivered_at + timedelta(
            days=rng.randint(0, 7), hours=rng.randint(0, 23)
        )
        reviews.append(
            {
                "review_id": review_id,
                "order_id": order["order_id"],
                "customer_id": order["customer_id"],
                "rating": rating,
                "comment": ctx.faker.sentence() if rating <= 3 or rng.random() < 0.5 else None,
                "occurred_at": iso(reviewed_at),
            }
        )
        review_id += 1

    return reviews


def generate_audit_events(
    ctx: Context, staff: list[dict[str, Any]], orders: list[dict[str, Any]], status_history: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rng = ctx.random
    staff_by_branch: dict[int, list[int]] = defaultdict(list)
    for member in staff:
        staff_by_branch[member["branch_id"]].append(member["staff_id"])
    branch_by_order = {o["order_id"]: o["branch_id"] for o in orders}

    events: list[dict[str, Any]] = []
    event_id = 1
    for entry in status_history:
        if entry["status"] not in AUDITABLE_STATUSES:
            continue
        branch_id = branch_by_order.get(entry["order_id"])
        candidates = staff_by_branch.get(branch_id, [])
        actor_staff_id = rng.choice(candidates) if candidates else None
        events.append(
            {
                "audit_event_id": event_id,
                "order_id": entry["order_id"],
                "actor_staff_id": actor_staff_id,
                "action": f"ORDER_{entry['status']}",
                "occurred_at": entry["occurred_at"],
            }
        )
        event_id += 1

    return events
