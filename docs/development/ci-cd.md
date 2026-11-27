# CI/CD

Reference for every GitHub Actions workflow in this repository: what it checks, when it
runs, and which branch-depth tier (master prompt §9) it implements. Each Phase 3 Task adds
its own section here as its workflow ships; see Epic #7 / `docs/architecture/README.md` for
the Phase this belongs to.

## Branch-depth model (§9)

| Branch depth | What it means | Workflow(s) |
|---|---|---|
| `feature/*`, `infrastructure/*`, `bugfix/*`, ... -> `test` | format/lint/type-check/unit-test/security | `quality-gate.yml` |
| `test` | full integration/E2E/container scan | `integration-validation.yml`, `container-scan.yml` (every PR into `test`, plus weekly) |
| `main` | production acceptance | `production-acceptance.yml` (`push` to `main` only — a post-merge gate, not a PR check) |
| `preview` -> `test` | dependency compatibility | `dependency-scan.yml`, plus `quality-gate.yml` (every PR into `test` is linted regardless of head branch) |

`branch-source-validation.yml` (Phase 0) is a prerequisite to all of the above: it restricts
*which* branch a PR may come from for a given base, so the right depth tier above always
applies to the right kind of change.

`secret-scan.yml` is cross-cutting rather than tied to one depth tier: it runs on every
`push`/`pull_request` regardless of branch, as the third of three independent secret-scanning
layers (see its own section below).

## `quality-gate.yml`

**Triggers:** `pull_request` targeting `test` (every PR, regardless of head branch).
**Permissions:** `contents: read`.

- `repo-hygiene` (always runs): lints every workflow file with `actionlint`
  (`reviewdog/action-actionlint`), every tracked YAML file with `yamllint`
  (config: `.yamllint.yml`), and every tracked Markdown file with `markdownlint-cli2`
  (config: `.markdownlint.jsonc`, with a directory-scoped override at
  `.github/ISSUE_TEMPLATE/.markdownlint.jsonc` for that directory's frontmatter-driven
  heading structure).
- `backend-quality`: real since Phase 5 (Task #108) — `ruff`/`black --check`/`mypy`/`pytest`
  against the throwaway `backend/health/` app, with a job-level `postgres:16-alpine` service
  (lighter than the full Compose stack `integration-validation.yml`'s `compose-validate` job
  brings up). Phase 6 (Epic #10) extends this with the real `apps/<domain>/` modules; the
  job itself needs no further changes.
- `frontend-quality`: real since Phase 5 (Task #109) — `eslint`/`prettier --check`/`tsc`
  (e2e harness)/`ng build smoke-app`/Vitest unit tests/Playwright e2e against the throwaway
  `projects/smoke-app/`. Phase 7 (Epic #11) repoints this at the real applications; the job
  itself needs no further changes.
- `dataset-generation`: real since Phase 5 (Task #112) — runs
  `scripts/dataset/generate.py --tier smoke --verify` on every PR into `test`. The
  `integration` and `load` tiers are deliberately never run in CI (master prompt §10: "must
  not overload CI") — see `scripts/dataset/README.md` for how those are proven instead.

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
  `infrastructure/compose/README.md` for local development, just scripted), brings the full
  stack up with `make up`, and polls `docker compose ps` until all ten healthchecked services
  report `healthy` (Phase 2's original five plus Phase 4's five observability services; fixed
  in Issue #106/#107 after the expected count was left stale post-Phase-4) or a 90s timeout is
  hit (Issue #55 observed ~20-35s on a real run). Teardown uses `make clean`
  (`down -v --remove-orphans`) rather than plain `make down`: Issue #55 deliberately validated
  that `make down` keeps named volumes for local/persistent use, but this job runs on an
  ephemeral runner with no reason to keep them, so it tears down completely and then asserts
  (via `docker volume ls`/`docker network ls` filtered on the job's `COMPOSE_PROJECT_NAME`)
  that nothing was left behind.
- `migration-upgrade-downgrade` ("Django migration upgrade/downgrade test"): real since
  Phase 5 (Task #110) — against a job-level `postgres:16-alpine` service (not the full
  Compose stack), applies every migration from empty, reverses the `health` app's migration
  back to zero, re-applies it, and asserts `showmigrations` shows no unapplied migration.
  Proves the upgrade/downgrade mechanism itself ahead of Phase 6 adding real business-domain
  migrations on top of it.
- `backend-frontend-integration` ("Backend/frontend integration tests (Playwright auth E2E)"):
  real since Phase 7 (Task #141, PR #147) — brings up its own full copy of the stack (same
  12/5 healthy-vs-no-healthcheck split as `compose-validate` above), then runs the Playwright
  auth E2E suite against it, independent of `compose-validate`'s own stack (which tears down
  with `if: always()` before this job could reuse it).

## Container image scanning

**`container-scan.yml` triggers:** `pull_request` targeting `test`, plus a weekly `schedule`
(Monday 04:00 UTC) so newly-disclosed CVEs are caught against the unchanged pinned images
between PRs. **Permissions:** `contents: read`, `security-events: write` (SARIF upload,
same as `codeql.yml`).

- `discover-images`: runs `docker compose -f infrastructure/compose/docker-compose.yml
  config --images` against a CI-only `.env` (same generation mechanism as
  `integration-validation.yml`) to derive the current image list at run time, so this
  workflow never drifts from whatever the Compose file actually pins — it picked up each of
  Phase 4's five observability images and both Phase 6/7 application Dockerfiles
  automatically, no workflow edit needed each time. The list is exposed as a job output
  consumed by the matrix below.
- `trivy-scan`: a `strategy.matrix` job, one entry per image from `discover-images`, each
  running `aquasecurity/trivy-action` with `severity: CRITICAL,HIGH` and `exit-code: 1`
  against the real pinned image. 17 images today: the 5 Phase 2 infrastructure images
  (`postgres`, `mongo`, `redis`, `rabbitmq`, `nginxinc/nginx-unprivileged`), the 2 Phase 6/7
  application images built from `backend/Dockerfile`/`frontend/Dockerfile`
  (`pizza-store-backend`, `pizza-store-frontend`), and the 10 Phase 4 observability images
  (`grafana`, `prometheus`, `alertmanager`, `loki`, `promtail`, `jaeger`, `otel-collector`,
  `postgres-exporter`, `mongodb-exporter`, `redis-exporter`). Each image's SARIF result is
  uploaded to the Security tab independently via `github/codeql-action/upload-sarif`, so one
  image's findings don't mask another's.

### `.trivyignore`

Scanning all 17 real images (rather than a synthetic placeholder) surfaces genuine
CRITICAL/HIGH CVEs — mostly vendor-published layers we don't build ourselves (Alpine base
packages, vendored Go modules in the observability images), each already fixed upstream but
not yet rebuilt into the vendor's published image.

`.trivyignore` documents each currently-known CVE, grouped by the package/binary
responsible, with a one-line reason per group — never a blanket severity downgrade. It is a
**living baseline, not a one-time waiver**: whenever Renovate's `docker` manager opens a PR
bumping one of these image tags/digests, this workflow re-scans the new build, and any entry
that no longer reproduces should be deleted in that same PR. A genuinely new CRITICAL/HIGH
finding not already listed here is exactly the signal this workflow exists to catch, and
should block the PR until reviewed, not be bulk-added to the ignore-list.

## SAST / code scanning

**`codeql.yml` triggers:** `pull_request` targeting `test`, plus a weekly `schedule`
(Monday 03:00 UTC) so query-coverage improvements are caught against otherwise-unchanged code.
**Permissions:** `contents: read`, `security-events: write` — the one workflow in this repo
that needs the latter, scoped only here, to upload SARIF results.

- `analyze` matrix job: `github/codeql-action` `init` + `analyze` for `actions`, `python`, and
  `javascript-typescript`. `actions` (scans `.github/workflows/*.yml`) runs unconditionally —
  it is also GitHub's own recommended default-setup language for this repository. `python`
  and `javascript-typescript` are guarded per-language with `hashFiles('backend/**/*.py')` /
  `hashFiles('frontend/**/*.ts')`: unlike the harmless echo placeholders elsewhere in this
  phase, CodeQL hard-errors ("CodeQL could not process any code written in \<language\>")
  rather than succeeding against an empty database when zero files of that language exist
  anywhere in the repo — confirmed on a real CI run before this guard was added. All three
  languages are genuinely active today against real content (Phase 6/7 added the backend/
  frontend source that makes the `python`/`javascript-typescript` guards permanently true);
  the guard itself is kept as-is since it is still correct, just no longer load-bearing.

**`sast.yml` triggers:** `pull_request` targeting `test`. **Permissions:** `contents: read`.

- `semgrep` job: runs `semgrep scan` with the `p/ci`, `p/dockerfile`, and `p/github-actions`
  registry rulesets directly inside the official `semgrep/semgrep` container image, pinned to
  a content digest (the image-pull equivalent of this repo's commit-SHA pinning convention
  for actions). `returntocorp/semgrep-action` — the Marketplace Action named in the original
  Task spec — is archived/deprecated upstream in favor of invoking the CLI directly, so this
  workflow does that instead of pinning a dead action. `p/ci` and `p/github-actions` have real
  targets today (this repo's own workflow files, `renovate.json`, `.github/dependabot.yml`);
  `p/dockerfile` has none yet (no `Dockerfile` exists before Phase 6/7) and is a no-op until
  then. A real run against this repository's content, pre-fix, caught one genuine finding —
  `.github/dependabot.yml` missing a Dependabot `cooldown` period — fixed in the same change
  that added this workflow, same pattern as the linters Task #70 added catching real
  pre-existing issues.
- `bandit` job: real since Phase 5 (Task #108, ahead of Phase 6's real modules) — runs
  unconditionally, no `hashFiles` guard. `bandit -r backend/ -x
  "backend/*/tests/*,backend/.venv"`, with B101 (assert)/B105/B106 (hardcoded test fixture
  passwords) findings expected and allowed in excluded test code.

## Dependency scanning and the Renovate `preview` flow

**`dependency-scan.yml` triggers:** `pull_request` targeting `test` (every PR, regardless of
head branch — same as `quality-gate.yml`). **Permissions:** `contents: read`.

- `pip-audit` / `npm-audit`: real since Phase 5 (Tasks #108/#109, ahead of Phase 6/7's real
  apps) — both run unconditionally, no `hashFiles` guard. `pip-audit` scans
  `backend/requirements*.txt`; `npm audit --omit=dev` scopes the frontend scan to runtime
  dependencies only, since dev-tooling CVEs are tracked separately via Renovate/Dependabot.

### Real bug found: `preview` had never been synced since repository bootstrap

`renovate.json` (Phase 0) restricts `baseBranches` to `["preview"]` so Renovate treats that
branch as the source of truth for current dependency versions. Verifying this Task's
Acceptance Criteria — a real, observed Renovate PR, not configuration review — surfaced that
`preview` had never received a single commit since the initial repository-bootstrap commit:
the Dependency Dashboard (Issue #1) reported "Detected Dependencies: None detected" because
`preview`'s tree predated `infrastructure/compose/docker-compose.yml` and every Phase 3
workflow's pinned-action references — there was nothing on that branch for Renovate's
managers to scan. Fixed by fast-forwarding `preview` to `test`'s current head (a clean
fast-forward; `preview` had made zero independent commits, so this is a pure sync, not a
merge with conflicts) before triggering the on-demand Renovate run described below. Going
forward, `preview` needs the same periodic catch-up from `test` whenever it has drifted far
enough that Renovate's scan would miss real dependency surfaces.

### Observed outcome

Once `preview` had real content, Renovate's own schedule (not the Dependency Dashboard's
manual-run checkbox — it ran before that was needed) opened two real PRs against `preview`
within minutes:

- PR #82 — `semgrep/semgrep` Docker digest bump (`sast.yml`'s pinned image, same tag, new
  digest)
- PR #83 — `python` 3.12 -> 3.15 (`quality-gate.yml`'s `actions/setup-python` step)

Both merged cleanly into `preview` (squash, no conflicts). The `preview -> test` promotion
(PR #84) carried exactly those two line changes — nothing else — and went green on every
applicable workflow (quality-gate, dependency-scan, SAST/CodeQL, container-scan).
`test -> main` (PR #85) promoted that plus the rest of Phase 3's work accumulated since the
last promotion (Tasks #70-#73) with every check green, confirming the full
`preview -> test -> main` chain works end to end with real, non-simulated changes.

Two operational notes from running this for the first time:

- `preview` must be treated as a long-lived branch like `test`/`main`, not a disposable
  feature branch — when promoting a PR whose head is `preview`, do not pass a
  delete-the-head-branch option to the merge; recreate immediately via the Git Data API
  (`POST /git/refs`) pointed at the current `test` tip if this is ever done by mistake, since
  `test` is always a superset of what `preview` held once a promotion lands.
- GitHub's branch-protection ruleset on `test`/`main` requires the triggering status check
  (`validate-source-branch`) to have run against the PR's current merge ref; if the base
  branch advances after a PR opens, the PR reports `BEHIND` and needs
  `PUT /pulls/{n}/update-branch` (or an equivalent manual sync) before it can merge, even
  though the underlying change has no real conflict.

## Production acceptance

**`production-acceptance.yml` triggers:** `push` targeting `main` only. Because
`branch-source-validation.yml` already restricts `main` to merge commits from already-CI-green
`test -> main` PRs, this workflow is deliberately a post-merge gate confirming what actually
landed on `main`, not a pre-merge PR check — the master-prompt §9 "production acceptance"
tier is about the commit now live on `main`, not a hypothetical merge result.
**Permissions:** `contents: read`.

- `compose-acceptance`: re-runs the exact same validate/boot/health-poll/teardown sequence as
  `integration-validation.yml`'s `compose-validate` job (see that section above), against
  `main`'s copy of the Compose file, as a final confirmation independent of whatever already
  ran on the `test -> main` PR itself.
- `deploy-readiness`: guarded on `hashFiles('backend/Dockerfile') != '' ||
  hashFiles('frontend/**/Dockerfile') != ''`. Both Dockerfiles now exist (Phase 6/7), so the
  guard is permanently true — but it still only echoes a message; no Phase 8 Task (#157-#161)
  ever scoped a real versioned image build/push step here. Phase 8 validated the VPS/Swarm/
  Kubernetes/Terraform deployment targets directly instead (`docs/deployment/`,
  `docs/cloud/`); this job is a deliberately out-of-scope placeholder, not a forgotten TODO —
  confirmed during the Issue #167 Phase 9 Gate audit.

## Secret scanning (three independent layers)

Per Epic #7's Security Requirements, this repository runs three independent secret-scanning
layers with no single point of failure:

1. **GitGuardian** — an account-wide GitHub App (pre-existing on the user's account, not set
   up as part of this project; see the Phase 0 notes in `docs/architecture/README.md`).
2. **GitHub native secret scanning + push protection** — a repository setting under
   `Settings -> Code security and analysis`. Confirmed already enabled on this repository
   (`secret_scanning: enabled`, `secret_scanning_push_protection: enabled` via the repository
   API) before this Task started; no toggle was needed.
3. **`secret-scan.yml`** (this Task) — an in-CI, repo-owned layer using `gitleaks/gitleaks-action`
   with the default ruleset. **Triggers:** every `push` and `pull_request`, with no branch
   filter, so it covers every branch this repository has, not just `test`/`main`.
   **Permissions:** `contents: read`. Checkout uses `fetch-depth: 0` so gitleaks scans full
   history rather than a shallow single-commit diff. `GITLEAKS_ENABLE_COMMENTS` is set to
   `"false"`: the action's PR-comment feature needs `pull-requests: write`, and this workflow
   deliberately stays read-only since findings already surface in the job log and step
   summary. No `GITLEAKS_LICENSE` is required — that's only for GitHub organization accounts,
   and this repository is on a personal account.

None of the three layers replaces another: GitGuardian and GitHub's native scanning operate
independently of this repository's own CI, while `secret-scan.yml` is the one layer whose
configuration (ruleset, comment behavior, triggers) this repository actually owns and can
version-control.
