# Shared

Framework-level, cross-cutting code only, per
[ADR 0004](../../docs/adr/0004-backend-module-and-frontend-feature-layout.md) — never
domain/business logic for a specific module (that belongs under `backend/apps/<module>/`).

## Contents

- `events/` — Transactional Outbox and idempotent-consumer base classes (Issue #130, Phase
  6), reused by every future publishing/consuming module per
  [ADR 0005](../../docs/adr/0005-event-topology-and-outbox-design.md):
  - `outbox.py` — `AbstractOutboxEvent`, the base `outbox_events` table every publishing
    module subclasses for its own concrete table.
  - `idempotent.py` — `AbstractProcessedEvent`, the base `processed_events` table every
    consuming module subclasses; its unique `(event_id, consumer_name)` constraint is what
    makes a redelivered event safe to process at most once.
  - `publisher.py` — `ConfirmedPublisher`, a publisher-confirmed `pika.BlockingConnection`
    wrapper knowing nothing about Outbox rows or Django models. `declare_exchange()` (Issue
    #176) idempotently declares a durable topic exchange before the first publish to it --
    exchange declaration is normally the consumer's job (`consumer.py::declare_topology`
    below), but a module's first-ever published event has no consumer yet to have declared it
    first.
  - `relay.py` — `relay_pending()`, the `SELECT ... FOR UPDATE SKIP LOCKED` poller that reads
    a concrete `AbstractOutboxEvent` subclass's pending rows and publishes them via
    `publisher.py`. Wired to `manage.py relay_outbox` by
    `shared/management/commands/relay_outbox.py`; first called for real by
    `apps.customers.services.registration_service.RegistrationService` (Issue #176) --
    exercised directly by `shared/tests/integration/test_outbox_and_idempotency.py`.
  - `consumer.py` — `IdempotentConsumer` base class plus `declare_topology()`, the
    `<queue>`/`<queue>.retry`/`<queue>.dlq` declaration helper implementing ADR 0005's
    30s/2m/10m backoff schedule.
- `api/` — the custom DRF exception handler and API-conventions-proof endpoint
  (Issue #128, Phase 6). See [docs/api/conventions.md](../../docs/api/conventions.md).
  `serializers.py::StrictSerializer` (Issue #176) is the base every module's input serializer
  subclasses to satisfy ADR 0006's "unknown/unexpected fields are rejected, not silently
  ignored" -- a plain `serializers.Serializer` otherwise drops any key in `initial_data` that
  isn't a declared field.
- `permissions/` — `base.py::TwoStepPermission` (Issue #175, Phase 10), the reusable DRF
  `BasePermission` every protected endpoint from here onward composes with: step one checks
  `request.user.has_rbac_permission(permission)` (does the user hold *any* role granting this
  permission at all); step two, in `has_object_permission`, re-queries
  `request.user.role_assignments_granting(permission)` and checks whether one of those
  assignments' `organization_id`/`branch_id` actually scopes the specific object being acted
  on. Scope is always re-derived from the object, never trusted from JWT claims alone, so a
  stale or ambiguous claim can't widen access. Calls only duck-typed methods on `request.user`
  — no import of `apps.identity`, per this directory's own charter above.
- `tests/integration/test_multi_tenant_isolation.py` (Issue #183, Phase 10 close-out) —
  `TwoStepPermission` proven end-to-end across every staff-facing resource Phase 10 built
  (`restaurants`, `branches`, `products`, `menu`), not just one module's own suite: two full
  organizations, each with a restaurant/branch/product/menu-category/menu-item, asserting
  every staff write/read endpoint rejects the other organization's/branch's staff with `403`
  in both directions, plus one sanity check that an unscoped grant (Super Admin) passes all of
  them. Mirrors `test_two_step_permission.py`'s unit-level coverage at the real-HTTP,
  cross-module level Epic #14's own Acceptance Criteria require.
