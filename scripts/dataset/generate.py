#!/usr/bin/env python3
"""24-month synthetic business dataset generator (master prompt §10, Issues #111/#112).

Pure Python + Faker, no Django dependency -- runs standalone, ahead of Phase 10's
real schema. Output is JSON Lines under --output-dir, one file per entity group.
--tier selects smoke/integration/load volumes; see entities/config.py's SCALE_PRESETS.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from entities.branches import generate_branches
from entities.campaigns import generate_birthday_campaigns, generate_general_campaigns
from entities.config import DEFAULT_SEED, SCALE_PRESETS, Context
from entities.operations import (
    generate_audit_events,
    generate_delivery_tracking,
    generate_inventory_movements,
    generate_loyalty_transactions,
    generate_reviews,
)
from entities.orders import generate_orders
from entities.payments import generate_payments
from entities.people import generate_couriers, generate_customers, generate_staff
from entities.products import generate_products
from entities.writer import JsonlWriter


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--tier", choices=sorted(SCALE_PRESETS), default="integration")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verify.py's checks against the just-generated output before exiting.",
    )
    return parser.parse_args(argv)


def write_all(output_dir: Path, files: dict[str, list[dict[str, Any]]]) -> None:
    for filename, records in files.items():
        with JsonlWriter(output_dir / filename) as writer:
            for record in records:
                writer.write(record)


def generate(seed: int, tier: str, output_dir: Path) -> dict[str, list[dict[str, Any]]]:
    config = SCALE_PRESETS[tier](seed=seed)
    ctx = Context(config)

    branches = generate_branches(ctx)
    products = generate_products(ctx)
    staff = generate_staff(ctx, [b["branch_id"] for b in branches])
    couriers = generate_couriers(ctx, [b["branch_id"] for b in branches])
    customers, addresses = generate_customers(ctx)

    general_campaigns = generate_general_campaigns(ctx)
    birthday_campaigns = generate_birthday_campaigns(ctx, customers)

    orders, order_items, status_history = generate_orders(
        ctx,
        branches,
        products,
        customers,
        addresses,
        couriers,
        general_campaigns,
        birthday_campaigns,
    )

    payments, refunds = generate_payments(ctx, orders, status_history)
    loyalty_transactions = generate_loyalty_transactions(ctx, orders, status_history, customers)
    inventory_movements = generate_inventory_movements(ctx, branches, products, orders, order_items)
    delivery_tracking = generate_delivery_tracking(ctx, branches, orders, status_history)
    reviews = generate_reviews(ctx, orders, status_history)
    audit_events = generate_audit_events(ctx, staff, orders, status_history)

    return {
        "branches.jsonl": branches,
        "products.jsonl": products,
        "staff.jsonl": staff,
        "couriers.jsonl": couriers,
        "customers.jsonl": customers,
        "customer_addresses.jsonl": addresses,
        "general_campaigns.jsonl": general_campaigns,
        "birthday_campaigns.jsonl": birthday_campaigns,
        "orders.jsonl": orders,
        "order_items.jsonl": order_items,
        "order_status_history.jsonl": status_history,
        "payments.jsonl": payments,
        "refunds.jsonl": refunds,
        "loyalty_transactions.jsonl": loyalty_transactions,
        "inventory_movements.jsonl": inventory_movements,
        "delivery_tracking.jsonl": delivery_tracking,
        "reviews.jsonl": reviews,
        "audit_events.jsonl": audit_events,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()

    files = generate(args.seed, args.tier, args.output_dir)
    write_all(args.output_dir, files)

    elapsed = time.monotonic() - started
    total_records = sum(len(records) for records in files.values())
    print(f"Wrote {total_records:,} records across {len(files)} files to {args.output_dir} in {elapsed:.1f}s")

    if args.verify:
        import verify as verify_module

        return verify_module.run(args.output_dir, tier=args.tier)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
