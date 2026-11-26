# Backend

Django modular monolith. Apps separated by domain (identity, customers, restaurants, branches, menu, products, pricing, cart, orders, payments, kitchen, inventory, couriers, delivery, loyalty, notifications, reviews, analytics, audit). Each module owns its own model/serializer/service/repository/API/permission/test structure.

## Current state (Phase 5, Task #108)

This is an intentionally minimal, throwaway skeleton — just enough real Django source to
prove the Pytest/pytest-django/Factory Boy/Faker test chain works end to end ahead of Phase 6
(Backend Foundation), which replaces everything below except `health/`'s endpoint with the
real `backend/apps/<domain>/` module layout from
[ADR 0004](../docs/adr/0004-backend-module-and-frontend-feature-layout.md).

- `config/` — Django project settings, URLs, WSGI entrypoint. Database credentials are read
  from environment variables only (`POSTGRES_*`), never hardcoded.
- `health/` — a plain top-level app, deliberately **not** placed under a future `apps/`
  path, with two purposes:
  - `GET /health/` — a liveness/readiness endpoint worth keeping past Phase 6 (useful for
    `nginx`/a load balancer later).
  - `HealthPing` model + migration + Factory Boy factory — exists purely so the pytest-django
    chain and the migration upgrade/downgrade test (Task #110) have something real to
    exercise, since no business-domain models exist until Phase 10.

## Running tests locally

```text
cd backend
python -m venv .venv && .venv/Scripts/activate  # or .venv/bin/activate on Linux/macOS
pip install -r requirements-dev.txt
# requires a reachable Postgres (POSTGRES_HOST/PORT/DB/USER/PASSWORD env vars)
python manage.py migrate
pytest
```

## Known gaps

- No `backend` Docker Compose service or Dockerfile exists yet — that is Phase 6/8 scope.
  `make migrate`/`make seed` remain non-functional until then; `make test-backend` runs
  directly against the local checkout instead of through Compose.
- No real business logic — Phase 10 (Core Business) onward.

> Status: Phase 5 — throwaway test-infrastructure skeleton (Task #108), real
> pytest/pytest-django/Factory Boy/Faker chain proven in CI. Phase 6 (Epic #10) restructures
> this into the real modular-monolith layout.
