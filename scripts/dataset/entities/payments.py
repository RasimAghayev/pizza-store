from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .config import Context
from .timeutil import iso

PAYMENT_METHODS = ["ONLINE_CARD", "CASH_ON_DELIVERY"]
PAYMENT_METHOD_WEIGHTS = [70, 30]


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def generate_payments(
    ctx: Context,
    orders: list[dict[str, Any]],
    status_history: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = ctx.random

    history_by_order: dict[int, dict[str, str]] = {}
    for entry in status_history:
        history_by_order.setdefault(entry["order_id"], {})[entry["status"]] = entry[
            "occurred_at"
        ]

    payments: list[dict[str, Any]] = []
    refunds: list[dict[str, Any]] = []
    payment_id = 1
    refund_id = 1

    for order in orders:
        order_id = order["order_id"]
        statuses_at = history_by_order.get(order_id, {})
        method = rng.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS, k=1)[0]

        if order["final_status"] == "PAYMENT_FAILED":
            payments.append(
                {
                    "payment_id": payment_id,
                    "order_id": order_id,
                    "idempotency_key": f"idem-{order_id:07d}",
                    "method": method,
                    "amount_minor": order["total_minor"],
                    "status": "FAILED",
                    "occurred_at": statuses_at["PAYMENT_FAILED"],
                }
            )
            payment_id += 1
            continue

        if "CONFIRMED" not in statuses_at:
            # Never reached payment confirmation (e.g. stalled before CONFIRMED) --
            # no payment record, matching real pre-payment-gate order states.
            continue

        this_payment_id = payment_id
        payments.append(
            {
                "payment_id": this_payment_id,
                "order_id": order_id,
                "idempotency_key": f"idem-{order_id:07d}",
                "method": method,
                "amount_minor": order["total_minor"],
                "status": "SUCCEEDED",
                "occurred_at": statuses_at["CONFIRMED"],
            }
        )
        payment_id += 1

        if order["final_status"] == "CANCELLED":
            cancelled_at = _parse(statuses_at["CANCELLED"])
            requested_at = cancelled_at + timedelta(minutes=rng.randint(5, 60))
            refunds.append(
                {
                    "refund_id": refund_id,
                    "order_id": order_id,
                    "payment_id": this_payment_id,
                    "amount_minor": order["total_minor"],
                    "reason": "ORDER_CANCELLED",
                    "requested_at": iso(requested_at),
                    "completed_at": iso(requested_at + timedelta(hours=rng.randint(1, 24))),
                }
            )
            refund_id += 1
        elif order["final_status"] == "REFUNDED":
            refunds.append(
                {
                    "refund_id": refund_id,
                    "order_id": order_id,
                    "payment_id": this_payment_id,
                    "amount_minor": order["total_minor"],
                    "reason": "CUSTOMER_REQUEST",
                    "requested_at": statuses_at["REFUND_PENDING"],
                    "completed_at": statuses_at["REFUNDED"],
                }
            )
            refund_id += 1

    return payments, refunds
