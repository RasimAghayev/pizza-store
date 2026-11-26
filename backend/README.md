# Backend

Django modular monolith. Apps separated by domain (identity, customers, restaurants, branches, menu, products, pricing, cart, orders, payments, kitchen, inventory, couriers, delivery, loyalty, notifications, reviews, analytics, audit). Each module owns its own model/serializer/service/repository/API/permission/test structure, per [ADR 0004](../docs/adr/0004-backend-module-and-frontend-feature-layout.md).

## Layout

- `apps/` — one subfolder per bounded-context module (see `apps/README.md`); the rest stay
  empty until Phase 10 (Core Business).
  - `identity/` — the first real bounded-context module (Issue #127): a custom
    `identity.User` (`AUTH_USER_MODEL`), RS256-signed JWT access/refresh tokens with refresh
    rotation and stolen-token-reuse detection (ADR 0006). Endpoints: `POST
    /api/v1/auth/login/`, `POST /api/v1/auth/refresh/`, `POST /api/v1/auth/logout/` — see
    [docs/api/conventions.md](../docs/api/conventions.md) for the request/response shape,
    error envelope, and throttle rates.
- `shared/` — framework-level cross-cutting code only (see `shared/README.md`): the
  Outbox/idempotent-consumer base classes and `relay_outbox` management command
  (`shared/events/`, `manage.py relay_outbox --model <app.Model> --exchange <name>` — Issue
  #130) and the DRF conventions (error envelope, API schema plumbing — Issue #128).
- `integrations/` — reserved for a module's explicit synchronous call into another module;
  genuinely empty until a real need exists (see `integrations/README.md`).
- `config/` — Django project settings, URLs, WSGI entrypoint. `SECRET_KEY`, the Postgres
  password, the Redis password, the RabbitMQ password, and the JWT RS256 private key are all
  read from Compose secret files (`/run/secrets/*`) via `_read_secret()` in
  `config/settings.py`, per [ADR 0006](../docs/adr/0006-security-architecture-baseline.md) —
  never hardcoded, never a plain env var once a real `backend` Compose service exists.
- `health/` — a plain top-level app, deliberately **not** placed under `apps/` (it is not a
  bounded-context module):
  - `GET /health/` — a liveness/readiness endpoint, kept permanently (used by this service's
    own Compose healthcheck; worth wiring into a load balancer later).
  - `HealthPing` model + migration + Factory Boy factory — exists purely so the
    pytest-django chain and the migration upgrade/downgrade test (Task #110) have something
    real to exercise, since no business-domain models exist until Phase 10.
  - `HealthOutboxEvent`/`HealthProcessedEvent` — throwaway concrete subclasses of
    `shared/events/`'s abstract Outbox/idempotent-consumer base models, used only to exercise
    that infrastructure end-to-end in tests (Issue #130); not a real domain event.

> **Reconciliation note (Issue #126):** Epic #10's own "Files & Directories" field lists
> top-level `backend/domain/`, `backend/infrastructure/`, `backend/events/` folders — that
> wording comes from the master prompt's original §7 sketch, written before
> [ADR 0004](../docs/adr/0004-backend-module-and-frontend-feature-layout.md) fixed the real
> decision: `domain/` and `events/` live **inside each** `apps/<module>/`, not as shared
> top-level folders. This repo follows ADR 0004, the later and more specific decision.

## Running

The `backend` Compose service builds from this directory's `Dockerfile` and runs behind the
root `Makefile`:

```text
make up          # starts the full stack, including backend
make migrate      # $(COMPOSE) exec backend python manage.py migrate
make test-backend # $(COMPOSE) exec backend pytest
make lint         # $(COMPOSE) exec backend ruff check .
```

To run directly against a local checkout instead (e.g. without Docker):

```text
cd backend
python -m venv .venv && .venv/Scripts/activate  # or .venv/bin/activate on Linux/macOS
pip install -r requirements-dev.txt
# requires a reachable Postgres (POSTGRES_HOST/PORT/DB/USER/PASSWORD env vars); outside
# Compose, _read_secret() falls back to the POSTGRES_PASSWORD env var
python manage.py migrate
pytest
```

## Known gaps

- `make lint` (root `Makefile`) runs both `exec backend ruff check .` and
  `exec frontend npm run lint` in sequence; the backend half now passes for real, but the
  whole target still exits non-zero because no `frontend` Compose service exists yet
  (Phase 7/Epic #11 scope) — run `docker compose -f infrastructure/compose/docker-compose.yml
  exec backend ruff check .` directly to check backend lint in isolation until then.
- No real business logic — Phase 10 (Core Business) onward.
- A production-grade WSGI/ASGI server (this Dockerfile's `CMD` still runs Django's
  development server) is Phase 8 (Deployment Infrastructure) scope.

> Status: Phase 6 (Epic #10) is complete — Issues #126-#130 (Compose service/Dockerfile,
> `identity` module, DRF/OpenAPI conventions, the JWT auth baseline, and the Outbox/
> idempotent-consumer baseline) are all merged. Issue #131 is this Epic's close-out
> re-verification task.
