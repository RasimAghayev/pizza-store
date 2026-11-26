# Synthetic dataset generator (Task #111/#112)

Generates a fully synthetic, 24-month business dataset for the pizza store domain: no real
personal data, ever. Pure Python + [Faker](https://faker.readthedocs.io/), no Django
dependency — it runs standalone, ahead of Phase 10's real schema, so later phases have
realistic data to build and test against before a live database exists.

## Usage

```sh
pip install -r scripts/dataset/requirements.txt
python scripts/dataset/generate.py [--seed 20261126] [--output-dir data/synthetic] [--tier integration] [--verify]
```

Or via the Makefile: `make dataset-smoke`, `make dataset-integration`, `make dataset-load`.

| Flag | Default | Meaning |
| --- | --- | --- |
| `--seed` | `20261126` | Seeds both the `random.Random` instance and the `Faker` instance. Same seed + same tier = byte-identical output, every run, on every machine. |
| `--output-dir` | `data/synthetic` | Where the `.jsonl` files are written. Gitignored — this is generated data, never committed. |
| `--tier` | `integration` | `smoke` (1% of `integration`, floored to a handful per entity — fast local loop, runs in CI on every PR), `integration` (master prompt §10's baseline volumes: 10 branches, 100+ products incl. 30+ pizza variants, 100+ staff, 50+ couriers, 20,000+ customers, 100,000+ orders), or `load` (5x `integration`, for on-demand performance testing — never run in routine CI). |
| `--verify` | off | Runs `verify.py`'s checks against the output just written before exiting non-zero on the first failing category. |

`python scripts/dataset/verify.py --data-dir data/synthetic --tier integration` can also be
run standalone against an existing output directory.

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
increasing), and — at the `integration`/`load` tiers only — volume thresholds against master
prompt §10's minimums.

Reproducibility is proven, not assumed: running the generator twice with the same `--seed`
and `--tier` into separate directories and diffing them produces zero differences, at every
tier (`smoke`, `integration`, and `load`).

## CI

`.github/workflows/quality-gate.yml`'s `dataset-generation` job runs `--tier smoke --verify`
on every PR into `test`. The `integration` and `load` tiers are deliberately never run in
CI (master prompt §10: "Smoke, integration and load datasets are separated; must not
overload CI") — they're proven locally and documented as real PR evidence instead. See
[`docs/testing/README.md`](../../docs/testing/README.md) for the full test strategy this
fits into, and the seed/reset procedure.

Loading this generated data into a live database is explicitly **not** this generator's
job — that's Phase 10's, once real Django/Postgres models exist to load into.
