# Shared

Framework-level, cross-cutting code only, per
[ADR 0004](../../docs/adr/0004-backend-module-and-frontend-feature-layout.md) — never
domain/business logic for a specific module (that belongs under `backend/apps/<module>/`).

## Contents

- `events/` — Transactional Outbox and idempotent-consumer base classes
  (Issue #130, Phase 6), reused by every future publishing/consuming module per
  [ADR 0005](../../docs/adr/0005-event-topology-and-outbox-design.md). Not added yet as of
  this file's creation (Issue #126) — see that Issue for status.
- `api/` — the custom DRF exception handler and API-conventions-proof endpoint
  (Issue #128, Phase 6). See [docs/api/conventions.md](../../docs/api/conventions.md).
