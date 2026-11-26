# Frontend

Angular CLI multi-app workspace. Phase 7 (Epic #11) adds the real `customer-web`,
`management-web`, and `courier-web` applications under `projects/`, each generated with
`ng generate application <app-name>` per
[ADR 0004](../docs/adr/0004-backend-module-and-frontend-feature-layout.md).

## Current state (Phase 5, Task #109)

This is an intentionally minimal, throwaway skeleton — just enough real Angular source to
prove the Vitest (unit) and Playwright (e2e) test chains work end to end ahead of Phase 7,
which replaces `projects/smoke-app/` with the real applications.

- `projects/smoke-app/` — a single throwaway Angular app (`ng generate application`), thrown
  away wholesale once Phase 7's real apps exist. Its only job is rendering a static `#status`
  element so there is something real for both test chains to exercise.
- `e2e/` — a **permanent** Playwright harness, kept past Phase 7. `e2e/playwright.config.ts`
  currently serves `smoke-app`; Phase 7 repoints its `webServer`/`baseURL` at the real
  `customer-web` app without otherwise changing this directory's structure.

## Running tests locally

```text
cd frontend
npm ci
npm run lint          # ESLint (@angular-eslint)
npx prettier --check .
npm run typecheck     # TypeScript, e2e/ harness
npx ng build smoke-app  # full Angular template type-check
npm test              # Vitest unit tests
npx playwright install --with-deps chromium
npm run e2e           # Playwright e2e against smoke-app
```

## Known gaps

- No `frontend` Docker Compose service or Dockerfile exists yet — that is Phase 7/8 scope.
  `make test-frontend`/`make lint` run through Compose (`$(COMPOSE) exec frontend ...`),
  consistent with every other Makefile target, and so remain non-functional until that
  service exists. Run tests/lint directly against the local checkout in the meantime — see
  "Running tests locally" above.
- No real application code — Phase 7 (Frontend Foundation) onward.

> Status: Phase 5 — throwaway test-infrastructure skeleton (Task #109), real
> Vitest/Playwright chains proven in CI. Phase 7 (Epic #11) replaces `smoke-app` with the
> real `customer-web`/`management-web`/`courier-web` applications; `e2e/` is kept.
