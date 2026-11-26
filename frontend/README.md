# Frontend

Angular CLI multi-app workspace (`@angular/core` `^22.3.0`, standalone components, no Zone.js),
per [ADR 0004](../docs/adr/0004-backend-module-and-frontend-feature-layout.md). Four projects
under `projects/`, each generated with `ng generate application <name>` / `ng generate
library shared`:

- `projects/customer-web/` — the primary end-user-facing app. The first app wired to the
  real backend auth API (Issue #140, `app.config.ts`) and, from Issue #141 onward, given a
  real login flow, a non-functional register skeleton, and route guarding (see "Auth UI and
  routing" below).
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
npm run e2e                # Playwright e2e against customer-web (ng serve, no backend needed)
                            # -- includes accessibility.spec.ts's axe-core scan of /login
```

`npm run e2e:auth` is deliberately not in this baseline sequence — it needs the full Compose
stack (backend + postgres + the edge) already running, not just `ng serve`. See "Auth-flow
E2E tests" below for the extra setup it requires.

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

## Auth UI and routing (Issue #141)

`customer-web`'s `app.routes.ts` defines four routes: `/login` and `/register` (public), a
guarded `/dashboard` placeholder, and a catch-all that redirects unknown paths to `/login`
(same fail-closed default as the guard itself). All three screen components are lazy-loaded
via `loadComponent`.

- `auth/login/` — a Reactive Forms (email + password) component wired to the real
  `AuthService.login()`. On success it navigates to `/dashboard`; on failure it renders the
  backend's real error message (e.g. "Invalid email or password.", or the throttle message
  on a 429) through shared's `ErrorDisplay`. Errors arrive already mapped to `ApiError` by
  `errorInterceptor` — see `app.config.ts`'s interceptor-order comment.
- `auth/register/` — a **UI-only, intentionally non-functional** skeleton. The backend has
  no registration endpoint (Issue #127 never added one), so this form's submit button is
  permanently `disabled` and wired to nothing, real or fake — see the comment in
  `register.ts`. Do not wire this up to a mock response; it must stay honestly broken until a
  real registration endpoint exists.
- `dashboard-placeholder/` — a placeholder landing page behind the guard, with a logout
  button calling `AuthService.logout()` and redirecting to `/login` regardless of whether the
  network call itself succeeds (the local auth state is already cleared either way — see
  `auth.service.ts`'s `logout()`).
- `auth.guard.ts` — a functional `CanActivateFn` reading `AuthService.isAuthenticated()`
  (a signal, `true` only after a real login/refresh success). Fails closed: any
  unauthenticated or ambiguous state redirects to `/login`, never falls open. **Known
  limitation:** this signal is in-memory only — there is no "whoami" endpoint yet to restore
  it across a page reload, so reloading `/dashboard` while genuinely still logged in
  (httpOnly cookies still valid server-side) still bounces to `/login`. Deferred; not part of
  this Task's scope.

## Responsive layout and accessibility (Issue #142)

`shared`'s `AppShell` (`src/lib/app-shell/`) is mobile-first: `app-shell.css`'s base rules
target the narrowest viewport, with a single `min-width: 600px` breakpoint (matching
`app-shell.ts`'s `HANDSET_QUERY`, `(max-width: 599.98px)`) adding wider-viewport styles —
never the reverse. Below 600px, `mat-sidenav` runs in `mode="over"` (closed by default,
toggled by a hamburger button in the toolbar) with Angular Material's own `cdk/a11y`
`FocusTrap` active automatically whenever it shows its backdrop (confirmed by reading
`@angular/material`'s `sidenav.mjs`: the drawer only creates/enables a `FocusTrapFactory` trap
when `opened && isShowingBackdrop()`, i.e. exactly the handset/`over` case) — no separate CDK
a11y wiring was needed in this component. At 600px and above, the nav is `mode="side"` and
persistently open, and the toggle button is not rendered.

`AppShell.isHandset` is a signal built from `@angular/cdk/layout`'s `BreakpointObserver` via
`toSignal(..., { requireSync: true })` — the current (2026) Angular-team-recommended pattern,
confirmed against `angular/components`' own updated responsive-sidenav example, which replaced
the older `MediaMatcher`/`async` pipe style with this same `toSignal` shape. `HANDSET_QUERY` is
a plain `(max-width: 599.98px)` string rather than CDK's `Breakpoints.Handset` constant: that
constant's combined orientation/resolution queries don't reliably re-match a headless
Playwright viewport resize (confirmed by testing both), while a single `max-width` query does.

A skip-to-content link (`app-shell.html`'s first element, before `mat-sidenav-container`) lets
keyboard/screen-reader users bypass the nav entirely; `<main id="app-shell-main"
tabindex="-1">` is the real focus target. The toolbar is wrapped in `<header>` and the drawer
carries `role="navigation"`/`"dialog"` plus a matching `aria-label` (swapping with
`isHandset()`, mirroring Angular Material's own schematic-generated sidenav), so both
landmarks are announced correctly in either layout.

`customer-web/src/app/app.html`'s standalone `<h1 id="app-name">` placeholder, left over from
Issue #138 and predating real routing, was removed: once Issue #141 gave every route its own
`<h1>` ("Log in" / "Register" / "Dashboard"), it produced two `<h1>`s per screen. The app name is
still visible — it was already rendered in `AppShell`'s toolbar since Issue #139 — so removing
the duplicate is a pure heading-hierarchy fix, not a loss of content. `management-web`/
`courier-web` keep their own `#app-name` placeholder unchanged: neither has a routed screen
yet (Phase 10/12 scope), so it remains each app's only, correct heading.

`frontend/e2e/tests/accessibility.spec.ts` runs `@axe-core/playwright`'s `AxeBuilder` against
the real rendered `/login` page (webServer: `ng serve`, same as `smoke.spec.ts`), scoped via
`.withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])` to exactly the WCAG
2.0/2.1/2.2 A+AA rule sets — axe-core's `best-practice` tag (e.g. the `region` rule) is
deliberately excluded, since it would flag the skip link's intentional landmark-free
placement. This scan's `color-contrast` rule is the real verification that Issue #139's
Material theme tokens (toolbar, buttons, form fields, links) meet WCAG AA's 4.5:1/3:1
thresholds on every control actually rendered on that page, rather than an assumption that
Material's M3 theming "should" already satisfy it.

### Auth-flow E2E tests

`e2e/tests/auth-flow.spec.ts` (run via `npm run e2e:auth`, config
`e2e/playwright.auth.config.ts`) exercises the real login flow through the real backend over
the same-origin edge from Issue #140 — unlike `playwright.config.ts`'s smoke test, it has no
`webServer` entry, because it needs the full Compose stack (`nginx`/`frontend`/`backend`/
`postgres`, at minimum) already running, not a bare `ng serve`. To run it locally:

```text
make up                      # from the repo root; wait for all services to report healthy
make migrate                 # fresh Postgres volumes have no schema until this runs
docker compose -f infrastructure/compose/docker-compose.yml --env-file .env \
  exec backend python manage.py shell -c "
from apps.identity.services.registration_service import RegistrationService
from apps.identity.models import User
email = 'e2e-auth@example.com'
if not User.objects.filter(email=email).exists():
    RegistrationService().register(email=email, password='correct-horse-battery-staple')
"
cd frontend && npm run e2e:auth
```

The fixture email/password are seeded via `RegistrationService` directly (the same
service-layer class the future real registration endpoint will use) rather than any mocked
or fake HTTP call — there is no registration endpoint to call instead. CI runs this same
sequence in `.github/workflows/integration-validation.yml`'s `backend-frontend-integration`
job, which brings up and tears down its own copy of the stack (independent of
`compose-validate`'s, which already tears its own down before this job could reuse it).

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
- The register screen is permanently non-functional until a real registration endpoint
  exists (see "Auth UI and routing" above). The auth guard's in-memory session signal does
  not survive a page reload — same section, "Known limitation".
- Issue #142's screen-level accessibility audit (semantic landmarks, focus styles, the axe-core
  scan) only covers `customer-web`'s real screens. `AppShell`'s responsive behavior itself
  (Issue #142's mobile-first nav) is shared infrastructure and already applies to
  `management-web`/`courier-web` too, even though those two apps have no real screens of their
  own yet to audit (Phase 10/12 scope, see above).

> Status: Phase 7 (Epic #11). Issue #138 — the real Angular workspace (`customer-web`,
> `management-web`, `courier-web`, `shared`) replaces the Phase 5 throwaway `smoke-app`
> skeleton (Task #109); `e2e/` is kept, repointed at `customer-web`. Issue #139 — the shared
> design system baseline (Material theme + `AppShell`/`Loading`/`ErrorDisplay`), consumed by
> all three apps. Issue #140 — the edge `nginx`/`frontend` Compose service and the
> `AuthService`/interceptor stack, wired into `customer-web` only. Issue #141 — the auth UI
> (login, non-functional register skeleton, `/dashboard` guard) in `customer-web`, plus the
> `auth-flow` Playwright suite against the live stack. Issue #142 — mobile-first responsive
> behavior in the shared `AppShell`, a WCAG 2.2 AA accessibility pass on `customer-web`'s real
> screens, and an `axe-core` accessibility scan added to the Playwright suite. Issue #143
> continues this Epic (close-out).
