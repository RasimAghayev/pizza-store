# Frontend

Angular CLI multi-app workspace (`@angular/core` `^22.3.0`, standalone components, no Zone.js),
per [ADR 0004](../docs/adr/0004-backend-module-and-frontend-feature-layout.md). Four projects
under `projects/`, each generated with `ng generate application <name>` / `ng generate
library shared`:

- `projects/customer-web/` — the primary end-user-facing app. The first app wired to the
  real backend auth API (Issue #140, `app.config.ts`) and, from Issue #141 onward, given a
  real login flow.
- `projects/management-web/` — the back-office app. Currently an empty shell (root component
  only); gets real screens from Phase 10 onward.
- `projects/courier-web/` — the courier-facing app. Currently an empty shell; gets real
  screens from Phase 12 onward.
- `projects/shared/` — framework-level cross-cutting Angular code shared by all three apps.
  Contains the design system baseline (Issue #139): a single Angular Material theme
  (`src/lib/theme/theme.scss`) and three components — `AppShell` (toolbar + static side nav +
  content region), `Loading` (indeterminate spinner with a message), `ErrorDisplay` (a dumb
  presentational alert). It also contains `AuthService` and the HTTP interceptor stack
  (Issue #140) — see the section below.

- `e2e/` — a **permanent** Playwright harness (kept past Phase 7). `e2e/playwright.config.ts`
  serves `customer-web` and asserts against its `#app-name` placeholder; later Tasks extend
  this suite with the real auth-flow and accessibility checks.

Each app's root component (`app.ts`/`app.html`) wraps its `#app-name` placeholder and
`<router-outlet />` in `shared`'s `AppShell`, and both `provideAnimationsAsync()` (required by
Angular Material) and the theme's global stylesheet are wired into each app's `app.config.ts`
/ `angular.json`. No real routes, auth, or responsive behavior yet — those are later Phase 7
Tasks' scope (see Issues #140-142).

## `shared`'s theme and its `.mat-typography` class

`theme.scss` calls `mat.theme(...)` to emit Material's `--mat-sys-*` CSS custom properties
(used by Material's own components) and separately calls `mat.typography-hierarchy(...)` under
a `.mat-typography` selector (each app's `<body>` carries this class) so plain elements
(`h1`-`h6`, `p`, ...) pick up the same type scale. These are two different Sass APIs with
incompatible config shapes: `mat.theme()` takes the raw inline config map, while
`mat.typography-hierarchy()` needs a resolved theme object from `mat.define-theme()` — see the
comment in `theme.scss` for why both calls are needed side by side.

The library resolves as the package name `shared` (`frontend/tsconfig.json`'s `paths` maps it
to `./dist/shared`, the classic Angular CLI multi-project workspace convention), so `ng build
shared` must run before building any of the three apps — `quality-gate.yml`'s
`frontend-quality` job does this before its three `ng build <app>` steps.

## Running tests locally

```text
cd frontend
npm ci
npm run lint              # ESLint (@angular-eslint), all four projects
npx prettier --check .
npm run typecheck         # TypeScript, e2e/ harness
npx ng build shared          # must run before any app build -- see "shared's theme" above
npx ng build customer-web    # full Angular template type-check, per app
npx ng build management-web
npx ng build courier-web
npm test                  # Vitest unit tests, all four projects
npx playwright install --with-deps chromium
npm run e2e                # Playwright e2e against customer-web
```

`ng build`/`ng serve` without a project name fail with "Cannot determine project for command"
once a workspace has more than one project — always pass the project name explicitly (`ng
build customer-web`, `ng serve customer-web`). `ng lint` and `ng test`'s bare forms are the
exception: each runs every project's target in sequence, which is what `npm run lint`/`npm
test` rely on.

## `frontend` Compose service and the interceptor/AuthService stack

`frontend/Dockerfile` is a two-stage build: a `node:26-alpine` stage runs `ng build shared`
then `ng build customer-web`, and a `nginxinc/nginx-unprivileged:1.27-alpine` stage (same
image/version as the edge `nginx`) serves the result as static files, with a
client-side-routing fallback (`frontend/nginx.conf`). `infrastructure/compose/
docker-compose.yml`'s `frontend` service builds this image; the edge `nginx` proxies `/` to
it and `/api/` to `backend` (both now joined to `edge-net`) — see
`infrastructure/nginx/conf.d/default.conf` and `docs/api/conventions.md`'s "`SameSite=Strict`
vs. cross-origin CORS" section.

Only `customer-web` is wired behind the edge so far (Issue #140); `management-web`/
`courier-web` are not yet reachable through `nginx`.

`projects/shared/src/lib/http/` and `projects/shared/src/lib/auth/` (consumed by
`customer-web`'s `app.config.ts` only, for now):

- `AuthService` (`auth/auth.service.ts`) wraps `POST /api/v1/auth/{login,refresh,logout}`
  with `X-Client-Type: browser` and `withCredentials: true`, per
  `docs/api/conventions.md`. Its `refreshOnce()` shares one in-flight refresh call across
  concurrent 401s instead of firing one per failed request.
- `csrfInterceptor` attaches `X-CSRFToken` (read from the `csrftoken` cookie) only on
  `refresh`/`logout` requests, matching the backend's CSRF scoping — never on `login`.
- `errorInterceptor` maps the backend's `{"error": {"code","message","details"}}` envelope
  into a typed `ApiError` (`http/api-error.ts`), meant to be passed to `ErrorDisplay`.
- `authRefreshInterceptor` retries a request exactly once after a 401 via
  `AuthService.refreshOnce()`, excluding the auth endpoints themselves; a second failure
  propagates without retrying again. Registered **before** `errorInterceptor` in
  `withInterceptors([...])` so it still sees the raw `HttpErrorResponse` — see the comment in
  `customer-web/src/app/app.config.ts`.

## Known gaps

- `make test-frontend`/`make lint` still don't work against the `frontend` Compose service:
  its runtime stage is a minimal static-file `nginx` image with no `npm`/Node.js in it by
  design (single-purpose containers — see Architecture Requirements in Issue #140), so
  `$(COMPOSE) exec frontend npm test`/`npm run lint` have nothing to exec against. Run
  tests/lint directly against the local checkout — see "Running tests locally" above.
- `Secure` cookies require HTTPS; the edge `nginx` added by Issue #140 does not terminate
  TLS (out of that Task's scope). A real browser hitting `http://localhost` will receive but
  not send back the `Secure`-flagged auth/CSRF cookies — see `docs/api/conventions.md`'s
  "Known limitation: `Secure` cookies require HTTPS" section. `curl -i` still proves the
  cookies are set correctly on a single request.
- `management-web`/`courier-web` are empty shells with no real screens — Phase 10/12 scope
  respectively — and are not wired behind the edge `nginx` yet.
- No auth UI, responsive layout, or accessibility pass yet — Issues #141-142.

> Status: Phase 7 (Epic #11). Issue #138 — the real Angular workspace (`customer-web`,
> `management-web`, `courier-web`, `shared`) replaces the Phase 5 throwaway `smoke-app`
> skeleton (Task #109); `e2e/` is kept, repointed at `customer-web`. Issue #139 — the shared
> design system baseline (Material theme + `AppShell`/`Loading`/`ErrorDisplay`), consumed by
> all three apps. Issue #140 — the edge `nginx`/`frontend` Compose service and the
> `AuthService`/interceptor stack, wired into `customer-web` only. Issues #141-143 continue
> this Epic.
