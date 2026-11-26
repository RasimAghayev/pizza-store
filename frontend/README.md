# Frontend

Angular CLI multi-app workspace (`@angular/core` `^22.3.0`, standalone components, no Zone.js),
per [ADR 0004](../docs/adr/0004-backend-module-and-frontend-feature-layout.md). Four projects
under `projects/`, each generated with `ng generate application <name>` / `ng generate
library shared`:

- `projects/customer-web/` — the primary end-user-facing app. The first app wired to the
  real backend auth API (Issue #140) and given a real login flow (Issue #141).
- `projects/management-web/` — the back-office app. Currently an empty shell (root component
  only); gets real screens from Phase 10 onward.
- `projects/courier-web/` — the courier-facing app. Currently an empty shell; gets real
  screens from Phase 12 onward.
- `projects/shared/` — framework-level cross-cutting Angular code shared by all three apps:
  the design system (theme, app-shell, loading/error-display components — Issue #139),
  `AuthService`, HTTP interceptors (Issue #140). Nothing beyond the default generated
  placeholder lives here yet.

Each app's root component (`app.ts`/`app.html`) currently renders only a static
`#app-name` placeholder plus a `<router-outlet />` — no design system, no auth, no real
routes yet; those are later Phase 7 Tasks' scope (see Issues #139-142).

- `e2e/` — a **permanent** Playwright harness (kept past Phase 7). `e2e/playwright.config.ts`
  serves `customer-web` and asserts against its `#app-name` placeholder; later Tasks extend
  this suite with the real auth-flow and accessibility checks.

## Running tests locally

```text
cd frontend
npm ci
npm run lint              # ESLint (@angular-eslint), all four projects
npx prettier --check .
npm run typecheck         # TypeScript, e2e/ harness
npx ng build customer-web    # full Angular template type-check, per app
npx ng build management-web
npx ng build courier-web
npm test                  # Vitest unit tests, all four projects
npx playwright install --with-deps chromium
npm run e2e                # Playwright e2e against customer-web
```

`ng build`/`ng test`/`ng serve` without a project name fail with "Cannot determine project
for command" once a workspace has more than one project — always pass the project name
explicitly (`ng build customer-web`, `ng serve customer-web`). `ng lint`'s bare form is the
one exception: it runs every project's lint target in sequence, which is what `npm run lint`
relies on.

## Known gaps

- No `frontend` Docker Compose service or Dockerfile exists yet — that is Issue #140's scope
  (wiring the edge `nginx` to a real `frontend` service serving `customer-web`).
  `make test-frontend`/`make lint` run through Compose (`$(COMPOSE) exec frontend ...`),
  consistent with every other Makefile target, and so remain non-functional until that
  service exists. Run tests/lint directly against the local checkout in the meantime — see
  "Running tests locally" above.
- `management-web`/`courier-web` are empty shells with no real screens — Phase 10/12 scope
  respectively.
- No design system, auth UI, HTTP interceptors, responsive layout, or accessibility pass yet
  — Issues #139-142.

> Status: Phase 7 (Epic #11), Issue #138 — the real Angular workspace (`customer-web`,
> `management-web`, `courier-web`, `shared`) replaces the Phase 5 throwaway `smoke-app`
> skeleton (Task #109); `e2e/` is kept, repointed at `customer-web`. Issues #139-143 continue
> this Epic.
