# Testing

Real test strategy and the dataset-generation process behind it (Phase 5, Tasks #108-112).
Epic #9's Acceptance Criteria requires "Smoke/integration/load datasets are separated" and
"The seed script must be idempotent (re-running it produces the same result, no
duplicates)" — this document records how both are satisfied today, not aspirationally.

## Test strategy overview

| Layer | What exists today | Where |
| --- | --- | --- |
| Unit | pytest/pytest-django/Factory Boy/Faker chain against the throwaway `health/` app (Task #108); Angular unit tests via `npm test` (Task #109). Both run in CI on every PR into `test`. | `backend/`, `frontend/projects/smoke-app/`, `.github/workflows/quality-gate.yml` (`backend-quality`/`frontend-quality` jobs) |
| Integration | Django migration upgrade/downgrade test against a real Postgres service container (Task #110); full Docker Compose stack bring-up/health/teardown (Task #74, Phase 2/3). | `.github/workflows/integration-validation.yml` |
| E2E | Playwright harness (`frontend/e2e/`) against the throwaway smoke-app, run headless in CI (Task #109). Real end-to-end flows against the actual application are Phase 7+ scope, once `frontend/` has real feature code to exercise. | `frontend/e2e/`, `.github/workflows/quality-gate.yml` (`frontend-quality` job) |
| Security | SAST (Semgrep), secret scanning (Gitleaks, GitGuardian), dependency scanning (`pip-audit`, `npm audit`), container image scanning (Trivy), CodeQL — all real, all run on every relevant PR. | `.github/workflows/sast.yml`, `secret-scan.yml`, `dependency-scan.yml`, `container-scan.yml`, `codeql.yml` |
| Performance/load | The `load` tier of the synthetic dataset generator below exists specifically to give later phases (Phase 10+) something realistic to load-test business logic against once it exists. No application-level load testing exists yet — there is no application to load-test until Phase 10. | `scripts/dataset/` |
| Regression | Every Task above ships with real CI evidence in its PR, not a manual claim; `.github/workflows/backup-restore-test.yml` repeats the Phase 4 backup/restore test on every relevant PR and on manual dispatch so that result stays current. | `.github/workflows/backup-restore-test.yml`, `docs/runbooks/backup-restore.md` |

Nothing above is aspirational: each row names the Task that built it and the workflow that
proves it still works.

## Dataset generation (Task #111/#112)

`scripts/dataset/generate.py` is a standalone Python + Faker script (no Django dependency)
that produces a fully synthetic, 24-month business dataset: 18 JSON Lines entity files
(branches, products, staff, couriers, customers, customer_addresses, general_campaigns,
birthday_campaigns, orders, order_items, order_status_history, payments, refunds,
loyalty_transactions, inventory_movements, delivery_tracking, reviews, audit_events),
following master prompt §10/§11's volumes and order-lifecycle state machine. See
[`scripts/dataset/README.md`](../../scripts/dataset/README.md) for the full entity list and
CLI reference.

### Tiers

`--tier {smoke,integration,load}` (default `integration`) scales every entity count from the
same master prompt §10 baseline:

| Tier | Volumes | Used for |
| --- | --- | --- |
| `smoke` | 1% of `integration`, floored to a handful per entity (e.g. ~1,000 orders) | Fast local dev loop; runs routinely in CI (`quality-gate.yml`'s `dataset-generation` job) on every PR into `test` |
| `integration` | Master prompt §10's baseline (10 branches, 100+ products incl. 30+ pizza variants, 100+ staff, 50+ couriers, 20,000+ customers, 100,000+ orders) | Local/manual runs; proven in Task #111, not run routinely in CI |
| `load` | 5x the `integration` volumes | On-demand performance/load testing only. **Never run in routine CI** — master prompt §10 explicitly requires "Smoke, integration and load datasets are separated; must not overload CI" |

Output lands under `data/synthetic/` (gitignored — generated data is never committed) unless
`--output-dir` overrides it.

### Reproducibility (the "idempotent seed script" requirement)

No real Django/Postgres schema exists yet (Phase 10 adds it), so "re-seeding never silently
duplicates or drifts data" is satisfied at the generator level, not the database level:
re-running `generate.py` with the same `--seed` and `--tier` produces **byte-identical**
output files every time, proven by running it twice into separate directories and diffing —
zero differences, at `smoke`, `integration`, and `load` scale alike. `verify.py` additionally
checks referential integrity, financial reconciliation, and status-history monotonicity
against any generated output, so a regression that silently corrupts data (not just output
drift) is also caught.

## Seed/reset procedure

```sh
make dataset-smoke         # ~2s locally; what CI runs on every PR into test
make dataset-integration   # the master prompt §10 baseline; minutes, not run in CI
make dataset-load          # 5x integration; on-demand performance testing only
```

Each target wraps `python scripts/dataset/generate.py --tier <tier> --verify` directly on the
host — there is no `dataset` Compose service, by design (the generator has no Django
dependency and nothing to containerize). Re-running any target overwrites `data/synthetic/`
with the same byte-identical content for the same seed; there is no "duplicate" state to
accumulate because nothing is loaded into a database yet.

**Loading this generated data into a live database is explicitly out of scope here** — that
is Phase 10's job, once real Django/Postgres models exist for `python manage.py seed` (today
a Compose-only placeholder, see `backend/README.md`) to load the generated `.jsonl` files
into.
