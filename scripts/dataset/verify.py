#!/usr/bin/env python3
"""Verification checks for the synthetic dataset produced by generate.py (Issue #111).

Fails loudly (non-zero exit, printed errors) on the first category of violation it
finds rather than asserting correctness was never actually checked.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

FK_CHECKS: list[tuple[str, str, str, str]] = [
    ("staff.jsonl", "branch_id", "branches.jsonl", "branch_id"),
    ("couriers.jsonl", "branch_id", "branches.jsonl", "branch_id"),
    ("customer_addresses.jsonl", "customer_id", "customers.jsonl", "customer_id"),
    ("birthday_campaigns.jsonl", "customer_id", "customers.jsonl", "customer_id"),
    ("birthday_campaigns.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("orders.jsonl", "customer_id", "customers.jsonl", "customer_id"),
    ("orders.jsonl", "branch_id", "branches.jsonl", "branch_id"),
    ("orders.jsonl", "address_id", "customer_addresses.jsonl", "address_id"),
    ("orders.jsonl", "courier_id", "couriers.jsonl", "courier_id"),
    ("order_items.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("order_items.jsonl", "product_id", "products.jsonl", "product_id"),
    ("order_status_history.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("payments.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("refunds.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("refunds.jsonl", "payment_id", "payments.jsonl", "payment_id"),
    ("loyalty_transactions.jsonl", "customer_id", "customers.jsonl", "customer_id"),
    ("loyalty_transactions.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("inventory_movements.jsonl", "branch_id", "branches.jsonl", "branch_id"),
    ("inventory_movements.jsonl", "product_id", "products.jsonl", "product_id"),
    ("delivery_tracking.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("delivery_tracking.jsonl", "courier_id", "couriers.jsonl", "courier_id"),
    ("reviews.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("reviews.jsonl", "customer_id", "customers.jsonl", "customer_id"),
    ("audit_events.jsonl", "order_id", "orders.jsonl", "order_id"),
    ("audit_events.jsonl", "actor_staff_id", "staff.jsonl", "staff_id"),
]

FULL_SCALE_MINIMUMS = {
    "branches.jsonl": 10,
    "products.jsonl": 100,
    "staff.jsonl": 100,
    "couriers.jsonl": 50,
    "customers.jsonl": 20_000,
    "orders.jsonl": 100_000,
}
FULL_SCALE_MIN_PIZZA_VARIANTS = 30


def _load(data_dir: Path, filename: str) -> list[dict[str, Any]]:
    path = data_dir / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def check_referential_integrity(data_dir: Path) -> list[str]:
    errors: list[str] = []
    id_caches: dict[tuple[str, str], set[Any]] = {}

    def ids_for(filename: str, id_field: str) -> set[Any]:
        key = (filename, id_field)
        if key not in id_caches:
            records = _load(data_dir, filename)
            id_caches[key] = {r[id_field] for r in records}
        return id_caches[key]

    for source_file, fk_field, target_file, target_id_field in FK_CHECKS:
        records = _load(data_dir, source_file)
        target_ids = ids_for(target_file, target_id_field)
        for record in records:
            value = record.get(fk_field)
            if value is None:
                continue
            if value not in target_ids:
                errors.append(
                    f"{source_file}: {fk_field}={value!r} does not resolve to any "
                    f"{target_id_field} in {target_file}"
                )
                if len(errors) > 20:
                    return errors

    orders = _load(data_dir, "orders.jsonl")
    general_ids = ids_for("general_campaigns.jsonl", "campaign_id")
    birthday_ids = ids_for("birthday_campaigns.jsonl", "birthday_campaign_id")
    for order in orders:
        campaign_id = order.get("applied_campaign_id")
        if campaign_id is None:
            continue
        pool = general_ids if order["applied_campaign_type"] == "GENERAL" else birthday_ids
        if campaign_id not in pool:
            errors.append(
                f"orders.jsonl: order {order['order_id']} applied_campaign_id={campaign_id!r} "
                f"({order['applied_campaign_type']}) does not resolve"
            )

    return errors


def check_financial_reconciliation(data_dir: Path) -> list[str]:
    errors: list[str] = []
    orders = _load(data_dir, "orders.jsonl")
    order_items = _load(data_dir, "order_items.jsonl")

    item_totals_by_order: dict[int, int] = {}
    for item in order_items:
        item_totals_by_order[item["order_id"]] = (
            item_totals_by_order.get(item["order_id"], 0) + item["line_total_minor"]
        )

    for order in orders:
        subtotal = item_totals_by_order.get(order["order_id"], 0)
        if subtotal != order["subtotal_minor"]:
            errors.append(
                f"orders.jsonl: order {order['order_id']} subtotal_minor="
                f"{order['subtotal_minor']} but items sum to {subtotal}"
            )
        expected_total = order["subtotal_minor"] + order["delivery_fee_minor"] - order["discount_minor"]
        if expected_total != order["total_minor"]:
            errors.append(
                f"orders.jsonl: order {order['order_id']} total_minor="
                f"{order['total_minor']} but subtotal+fee-discount={expected_total}"
            )
        if len(errors) > 20:
            return errors

    return errors


def check_status_history_monotonic(data_dir: Path) -> list[str]:
    errors: list[str] = []
    history = _load(data_dir, "order_status_history.jsonl")
    by_order: dict[int, list[tuple[str, datetime]]] = {}
    for entry in history:
        by_order.setdefault(entry["order_id"], []).append(
            (entry["status"], _parse(entry["occurred_at"]))
        )

    for order_id, entries in by_order.items():
        previous_ts = None
        for status, ts in entries:
            if previous_ts is not None and ts <= previous_ts:
                errors.append(
                    f"order_status_history.jsonl: order {order_id} status {status} at "
                    f"{ts.isoformat()} is not strictly after the previous entry"
                )
                if len(errors) > 20:
                    return errors
            previous_ts = ts

    return errors


def check_volume_thresholds(data_dir: Path, scale: str) -> list[str]:
    if scale != "full":
        return []
    errors: list[str] = []
    for filename, minimum in FULL_SCALE_MINIMUMS.items():
        count = len(_load(data_dir, filename))
        if count < minimum:
            errors.append(f"{filename}: has {count} records, expected at least {minimum}")

    products = _load(data_dir, "products.jsonl")
    pizza_variants = sum(1 for p in products if p["category"] == "pizza_variant")
    if pizza_variants < FULL_SCALE_MIN_PIZZA_VARIANTS:
        errors.append(
            f"products.jsonl: has {pizza_variants} pizza_variant records, expected at "
            f"least {FULL_SCALE_MIN_PIZZA_VARIANTS}"
        )

    return errors


def run(data_dir: Path, scale: str) -> int:
    checks = [
        ("referential integrity", check_referential_integrity(data_dir)),
        ("financial reconciliation", check_financial_reconciliation(data_dir)),
        ("status-history monotonicity", check_status_history_monotonic(data_dir)),
        ("volume thresholds", check_volume_thresholds(data_dir, scale)),
    ]

    any_failed = False
    for name, errors in checks:
        if errors:
            any_failed = True
            print(f"FAILED: {name} ({len(errors)} issue(s))")
            for error in errors[:20]:
                print(f"  - {error}")
        else:
            print(f"OK: {name}")

    return 1 if any_failed else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--scale", choices=["smoke", "full"], default="full")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.data_dir, args.scale)


if __name__ == "__main__":
    raise SystemExit(main())
