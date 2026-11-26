# Synthetic dataset generator (Task #111)

Generates a fully synthetic, 24-month business dataset for the pizza store domain: no real
personal data, ever. Pure Python + [Faker](https://faker.readthedocs.io/), no Django
dependency — it runs standalone, ahead of Phase 10's real schema, so later phases have
realistic data to build and test against before a live database exists.

## Usage

```sh
pip install -r scripts/dataset/requirements.txt
python scripts/dataset/generate.py [--seed 20261126] [--output-dir data/synthetic] [--scale full] [--verify]
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--seed` | `20261126` | Seeds both the `random.Random` instance and the `Faker` instance. Same seed + same scale = byte-identical output, every run, on every machine. |
| `--output-dir` | `data/synthetic` | Where the `.jsonl` files are written. Gitignored — this is generated data, never committed. |
| `--scale` | `full` | `smoke` (a few hundred orders, fast local loop) or `full` (master prompt §10's baseline volumes: 10 branches, 100+ products incl. 30+ pizza variants, 100+ staff, 50+ couriers, 20,000+ customers, 100,000+ orders). |
| `--verify` | off | Runs `verify.py`'s checks against the output just written before exiting non-zero on the first failing category. |

`python scripts/dataset/verify.py --data-dir data/synthetic --scale full` can also be run
standalone against an existing output directory.

## What gets generated

Eighteen JSON Lines files, one per entity, written in dependency order so foreign keys
always resolve to a record already on disk:

`branches`, `products` (drinks/sides/desserts plus pizza size×crust×topping variants),
`staff`, `couriers`, `customers`, `customer_addresses` (customers may relocate mid-window),
`general_campaigns`, `birthday_campaigns`, `orders`, `order_items`, `order_status_history`,
`payments`, `refunds`, `loyalty_transactions`, `inventory_movements`, `delivery_tracking`,
`reviews`, `audit_events`.

Orders follow master prompt §11's full lifecycle state machine (`DRAFT_CART` through
`DELIVERED`, with deterministic branches into `PAYMENT_FAILED`, `CANCELLED`,
`REFUND_PENDING`/`REFUNDED`, and truncated "stalled" orders) so every downstream table
(payments, refunds, loyalty, audit events) reflects a real, consistent order outcome rather
than a random label. Money is always plain integer minor units — never float, never
Decimal — per CLAUDE.md's money rule; no fractional arithmetic is ever needed at this layer.

## Reproducibility and verification

`verify.py` checks four categories against any generated output: referential integrity
(every foreign key, including the orders table's polymorphic `applied_campaign_id`,
resolves), financial reconciliation (order totals reconcile against their line items),
status-history monotonicity (timestamps within an order's history are always strictly
increasing), and — at `--scale full` only — volume thresholds against master prompt §10's
minimums.

Reproducibility is proven, not assumed: running the generator twice with the same `--seed`
and `--scale` into separate directories and diffing them produces zero differences, at both
`smoke` and `full` scale.

## Where this goes next (Task #112)

This generator's `--scale` mechanism (`entities/config.py`'s `SCALE_PRESETS` dict) is the
extension point Task #112 uses to add the named `smoke`/`integration`/`load` CI tiers that
master prompt §10 and Epic #9's acceptance criteria require, plus a CI job that runs the
smallest tier with `--verify` on every relevant PR, `make dataset-<tier>` Makefile targets,
and the real `docs/testing/` documentation. Loading this generated data into a live database
is explicitly **not** this generator's job — that's Phase 10's, once real Django/Postgres
models exist to load into.
