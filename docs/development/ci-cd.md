# CI/CD

Reference for every GitHub Actions workflow in this repository: what it checks, when it
runs, and which branch-depth tier (master prompt §9) it implements. Each Phase 3 Task adds
its own section here as its workflow ships; see Epic #7 / `docs/architecture/README.md` for
the Phase this belongs to.

## Branch-depth model (§9)

| Branch depth | What it means | Workflow(s) |
|---|---|---|
| `feature/*`, `infrastructure/*`, `bugfix/*`, ... -> `test` | format/lint/type-check/unit-test/security | `quality-gate.yml` |
| `test` | full integration/E2E/container scan | `integration-validation.yml`, `container-scan.yml` |
| `main` | production acceptance | `production-acceptance.yml` |
| `preview` -> `test` | dependency compatibility | `dependency-scan.yml`, plus `quality-gate.yml` (every PR into `test` is linted regardless of head branch) |

`branch-source-validation.yml` (Phase 0) is a prerequisite to all of the above: it restricts
*which* branch a PR may come from for a given base, so the right depth tier above always
applies to the right kind of change.

## `quality-gate.yml`

**Triggers:** `pull_request` targeting `test` (every PR, regardless of head branch).
**Permissions:** `contents: read`.

- `repo-hygiene` (always runs): lints every workflow file with `actionlint`
  (`reviewdog/action-actionlint`), every tracked YAML file with `yamllint`
  (config: `.yamllint.yml`), and every tracked Markdown file with `markdownlint-cli2`
  (config: `.markdownlint.jsonc`, with a directory-scoped override at
  `.github/ISSUE_TEMPLATE/.markdownlint.jsonc` for that directory's frontmatter-driven
  heading structure).
- `backend-quality` / `frontend-quality`: guarded on `hashFiles('backend/**')` /
  `hashFiles('frontend/**')`. Inert today (those directories don't exist yet); Phase 6
  (Epic #10) and Phase 7 (Epic #11) wire the real `ruff`/`black`/`mypy`/`pytest` and
  `eslint`/`prettier`/`tsc`/jest steps into these jobs without needing to touch the trigger
  or permissions block above.

### Third-party action pinning convention

Every third-party action referenced by any Phase 3 workflow is pinned to a full commit SHA,
not a tag, with a trailing `# vX.Y.Z` comment naming the human-readable release the SHA
corresponds to. Renovate's `github-actions` manager tracks the pinned digest and opens an
update PR (targeting `preview`, per `renovate.json`) when a newer release is published — the
comment is for humans reading the diff, not something Renovate parses.

## `integration-validation.yml`

**Triggers:** `push` targeting `test` (every merge into `test` is validated immediately) and
`pull_request` targeting `main` (every `test -> main` promotion re-validates the stack before
it reaches production).
**Permissions:** `contents: read`.

- `compose-validate`: validates `infrastructure/compose/docker-compose.yml` with
  `docker compose config`, generates CI-only secret files and a CI-only `.env` from the
  tracked `*.example` templates (the same mechanism documented in
  `infrastructure/compose/README.md` for local development, just scripted), brings the Phase
  2 stack up with `make up`, and polls `docker compose ps` until all five services report
  `healthy` or a 90s timeout is hit (Issue #55 observed ~20-35s on a real run). Teardown uses
  `make clean` (`down -v --remove-orphans`) rather than plain `make down`: Issue #55
  deliberately validated that `make down` keeps named volumes for local/persistent use, but
  this job runs on an ephemeral runner with no reason to keep them, so it tears down
  completely and then asserts (via `docker volume ls`/`docker network ls` filtered on the
  job's `COMPOSE_PROJECT_NAME`) that nothing was left behind.
- `backend-frontend-integration`: guarded on `hashFiles('backend/**')` /
  `hashFiles('frontend/**')`, same pattern as `quality-gate.yml`. Placeholder today; Phase 6
  (Epic #10) wires Django migration checks and API integration tests against the live stack
  validated by `compose-validate`, and Phase 7 (Epic #11) adds Angular e2e smoke tests.
