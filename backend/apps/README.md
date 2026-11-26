# Apps

One subfolder per ADR 0001 bounded-context module (`identity`, `customers`, `restaurants`,
`branches`, `menu`, `products`, `pricing`, `cart`, `orders`, `payments`, `kitchen`,
`inventory`, `couriers`, `delivery`, `loyalty`, `notifications`, `reviews`, `analytics`,
`audit`), each following the exact subfolder layout fixed by
[ADR 0004](../../docs/adr/0004-backend-module-and-frontend-feature-layout.md):
`domain/`, `models/`, `repositories/`, `services/`, `api/`, `permissions/`, `events/`,
`migrations/`, `tests/{unit,integration}/`, `factories.py`, `README.md`.

`identity` (Phase 6, Issue #127) is the first module built on this layout and sets the
concrete precedent every later module copies.

Note: ADR 0004 supersedes the master prompt's original top-level sketch
(`backend/domain/`, `backend/infrastructure/`, `backend/events/` as shared top-level
folders) — `domain/` and `events/` live **inside each** module below, not as standalone
top-level directories. See `backend/README.md` for the full reconciliation note.
