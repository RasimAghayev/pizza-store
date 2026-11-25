# ADR 0004: Backend Module and Frontend Feature Layout

## Status

Accepted

## Context

ADR 0001 fixes the backend as a modular monolith with one Django app per bounded context
(identity, customers, restaurants, branches, menu, products, pricing, cart, orders, payments,
kitchen, inventory, couriers, delivery, loyalty, notifications, reviews, analytics, audit) and
requires Clean Architecture, DDD, Repository Pattern, Service Layer, and Dependency Injection
at the code level, not just at the deployment-unit level. Master prompt §7 fixes the top-level
repository layout (`backend/apps/`, `frontend/customer-web/`, `frontend/management-web/`,
`frontend/courier-web/`, `frontend/shared/`, etc.) and says "each module owns its own model/
serializer/service/repository/API/permission/test structure", but does not fix what the inside
of one module looks like.

Without this decision made once, up front, Phase 6's first module (identity, small) and a
later module (orders or audit, large) would end up structured differently depending on
whichever agent session implements each one — making the codebase inconsistent and harder to
navigate across modules.

No backend or frontend code exists yet; this ADR is written purely from the constraints in
ADR 0001 and master prompt §7.

## Decision

### Backend: layout inside one Django app

Every app under `backend/apps/<domain>/` uses the same fixed subfolder layout, regardless of
the module's current size — small modules start with near-empty subfolders rather than flat
files, so no module needs restructuring later just because it grew:

```text
backend/apps/<domain>/
├── domain/            # Pure business logic: entities, value objects, domain services,
│                      # business rule validation. No Django/DRF/infrastructure imports.
├── models/            # Django ORM models (persistence mapping only), one file per aggregate.
├── repositories/       # Repository Pattern: translate between domain objects and ORM models,
│                      # one file per aggregate. Only layer allowed to issue ORM queries.
├── services/          # Application services: one entry point per use case, orchestrate
│                      # repositories + domain layer + event publishing. Views call only this
│                      # layer, never repositories or models directly.
├── api/
│   ├── serializers.py  # Or serializers/ once it would otherwise exceed one file.
│   ├── views.py        # Or views/ under the same condition.
│   └── urls.py
├── permissions/        # DRF permission classes for this module.
├── events/             # Domain event classes this module publishes/consumes, and the
│                      # publisher adapter (see ADR 0001 — RabbitMQ + Outbox).
├── migrations/         # Django-managed.
├── admin.py
├── apps.py
├── tests/
│   ├── unit/           # domain/ and services/ logic, no DB.
│   ├── integration/    # repositories/ and api/ against a real test database.
│   └── factories.py
└── README.md           # One-paragraph module purpose + its published events, per the
                       # cross-file dependency comment convention (CLAUDE.md).
```

A single file inside a subfolder (e.g. `services/order_service.py` alone) is a normal,
expected state for a small module — the folder exists for consistency and so growth never
requires a breaking restructure, not because every module must have many files from day one.

### Backend: cross-module import restriction

`import-linter` (the `lint-imports` tool) is adopted, configured in
`backend/setup.cfg` (`[importlinter]` section), with one `forbidden` contract per pair of
modules that must stay decoupled per ADR 0001, plus one blanket `layers` contract per module
enforcing `domain` → `repositories`/`services` → `api` (inner layers never import outer ones).

Rule: `apps.<domain_a>` may import from `apps.<domain_b>.events` (event/message schemas only —
needed to deserialize events it consumes) and from `shared/` (framework-level cross-cutting
code only), but never from `apps.<domain_b>.models`, `.repositories`, `.services`, or
`.domain`. Modules that need another module's current state read-only in the same request
(e.g. pricing needing a product's active price) go through that module's `services/` entry
point, called explicitly and sparingly — the default remains asynchronous communication via
domain events (ADR 0001), and any such synchronous read is called out by name in that module's
README per the cross-file dependency comment convention.

This contract set is written now so Phase 6 modules are built against it from the start; the
CI job that runs `lint-imports` against it is added in Phase 3 (CI/CD & Quality, per Issue
#7/Epic Phase 3) — this ADR does not itself add CI.

### Frontend: feature layout inside one Angular app

`frontend/shared/` (fixed by master prompt §7) holds code shared **across** `customer-web/`,
`management-web/`, and `courier-web/` — design tokens, generic UI primitives, HTTP
interceptor base classes. It is a separate concern from the per-app layout below, which is
**internal to one app** (e.g. inside `customer-web/` only):

```text
<app>/src/app/
├── core/                    # App-wide singletons: auth/session service, HTTP interceptors,
│                            # route guards, app config. Imported once, in the root module/
│                            # bootstrap — never imported by a feature's inner components.
├── shared/                  # Presentational-only: reusable components/pipes/directives with
│                            # zero business logic and zero feature-specific state. Promoted
│                            # here only after a second feature needs the same piece.
└── features/
    └── <feature>/
        ├── data-access/      # Feature state (signals/store), API services, DTOs/mappers.
        ├── feature/          # Smart/container components and pages (routed).
        ├── ui/               # Dumb components used only within this feature.
        ├── <feature>.routes.ts
        └── index.ts          # Public API barrel — the only thing another feature may import.
```

`shared/` avoids becoming a dumping ground via two rules, both enforced by lint (see below):
a component/pipe/directive moves into `shared/` only once a second feature needs it unchanged
(no speculative promotion), and nothing with feature-specific business logic or feature state
is allowed into `shared/` regardless of reuse count — that case is a sign the logic belongs in
a third feature's `data-access/`, or in `core/` if it is truly app-wide.

### Frontend: cross-feature import restriction

`eslint-plugin-boundaries` is adopted (ESLint config per app, under `frontend/<app>/
.eslintrc` or the shared root config with per-app overrides) with element types `core`,
`shared`, and `feature`, and rules: a `feature` may import `core` and `shared` freely, but may
import another `feature` **only** through that feature's `index.ts` barrel, never via a deep
path into its `data-access/`, `feature/`, or `ui/` subfolders. As with the backend lint rule,
wiring this into CI is Phase 3 work; this ADR fixes the rule itself.

## Reason

- A fixed subfolder layout applied uniformly, even to currently-small modules, means no module
  needs a breaking restructure later purely because it grew — consistency is cheap to keep
  from the start and expensive to retrofit across 18 modules.
- Separating `domain/` from `models/` and routing all queries through `repositories/` is what
  makes the Repository Pattern and Clean Architecture commitments in ADR 0001 real in code,
  not just a stated intention — without this split, Django's ORM convenience methods (`.objects.filter(...)`) would end up called directly from views/services, erasing the boundary.
- `import-linter` and `eslint-plugin-boundaries` turn "modules stay decoupled" and "features
  stay decoupled" from a code-review-time hope into a mechanically checked rule, which matters
  more here than in a typical project because ADR 0001's eventual-microservice-extraction
  option depends on module boundaries having stayed real.
- Restricting cross-feature frontend imports to a barrel file (`index.ts`) keeps each
  feature's internal structure free to change without breaking other features, mirroring the
  backend's "services are the only public entry point" rule.

## Consequences

- Every new backend module (starting with identity in Phase 6) is created from the same
  subfolder skeleton; a module template/generator can be added later as a convenience, but is
  not required by this ADR.
- Code review must reject a service/view that imports another module's `repositories/` or
  `models/` directly, and reject a feature that deep-imports another feature's internals —
  until the Phase 3 lint jobs exist, this is a manual review responsibility.
- The identity module (Phase 6's first module) sets the concrete precedent other modules copy;
  if it reveals a gap in this layout, that gap is fixed via an ADR amendment, not by silently
  diverging per module.

## Alternatives

- **Flat app structure, no sub-layering** (`models.py`, `serializers.py`, `services.py`,
  `views.py` directly in each app, Django's own default convention): rejected — works for a
  small module, but a large module (orders, payments) would outgrow a single `services.py` or
  `models.py` long before the project matures, and different modules would hit that threshold
  at different times, re-creating the inconsistency this ADR exists to prevent.
- **One shared `common` app for all cross-cutting backend code**: rejected — in practice this
  becomes an uncontrolled dumping ground, creates an implicit coupling point every module
  depends on, and makes it unclear whether code placed there is genuinely framework-level or
  domain logic that was lazily moved out of its owning module — directly undermining the
  bounded-context isolation ADR 0001 is built on.
- **Nx-style enforced module boundaries for both backend and frontend**: rejected for now —
  master prompt §7 does not adopt an Nx monorepo, Django's app namespace already gives the
  backend enough structural isolation, and `import-linter`/`eslint-plugin-boundaries` give the
  same enforcement guarantee at far lower adoption cost than introducing a new build-system
  layer at Phase 1.
