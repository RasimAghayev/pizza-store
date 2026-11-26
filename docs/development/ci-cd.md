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

## Container image scanning

**`container-scan.yml` triggers:** `pull_request` targeting `test`, plus a weekly `schedule`
(Monday 04:00 UTC) so newly-disclosed CVEs are caught against the unchanged pinned images
between PRs. **Permissions:** `contents: read`, `security-events: write` (SARIF upload,
same as `codeql.yml`).

- `discover-images`: runs `docker compose -f infrastructure/compose/docker-compose.yml
  config --images` against a CI-only `.env` (same generation mechanism as
  `integration-validation.yml`) to derive the current image list at run time, so this
  workflow never drifts from whatever Phase 2's Compose file actually pins. The list is
  exposed as a job output consumed by the matrix below.
- `trivy-scan`: a `strategy.matrix` job, one entry per image from `discover-images`, each
  running `aquasecurity/trivy-action` with `severity: CRITICAL,HIGH` and `exit-code: 1`
  against the real pinned image (`postgres:16-alpine`, `mongo:7`, `redis:7-alpine`,
  `rabbitmq:3-management-alpine`, `nginxinc/nginx-unprivileged:1.27-alpine` as of Phase 2 —
  no application Dockerfile exists yet; Phase 6/7/8 will add those and this workflow picks
  them up automatically once they appear in the Compose file). Each image's SARIF result is
  uploaded to the Security tab independently via `github/codeql-action/upload-sarif`, so one
  image's findings don't mask another's.

### `.trivyignore`

Scanning the five real images (rather than a synthetic placeholder) surfaces genuine
CRITICAL/HIGH CVEs today — all of them in vendor-published layers we don't build ourselves
(Alpine base packages, and the `gosu`/mongo-tool Go binaries and `js-yaml` bundled by the
official postgres/mongo images). Every one of them already has a fix published by the
upstream package maintainer (Alpine, Go, npm); what's missing is the vendor image being
rebuilt on top of that fix, which is outside this repository's control.

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
  it is also GitHub's own recommended default-setup language for this repository — and is the
  one entry that is genuinely active today, against real content. `python` and
  `javascript-typescript` are guarded per-language with `hashFiles('backend/**/*.py')` /
  `hashFiles('frontend/**/*.ts')`: unlike the harmless echo placeholders elsewhere in this
  phase, CodeQL hard-errors ("CodeQL could not process any code written in \<language\>")
  rather than succeeding against an empty database when zero files of that language exist
  anywhere in the repo — confirmed on a real CI run before this guard was added. Both
  self-activate, no workflow edit needed, the moment Phase 6/7 add real source matching their
  pattern; until then, Epic #7's "CodeQL code scanning is active" criterion is satisfied by
  the `actions` language only, same deferral already true for the `python`/
  `javascript-typescript` halves of `backend-quality`/`frontend-quality`/`bandit` elsewhere in
  Phase 3.

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
- `bandit` job: guarded on `hashFiles('backend/**')`, same placeholder pattern as the other
  Phase 3 workflows. Inert until Phase 6 wires `bandit -r backend/`.

## Dependency scanning and the Renovate `preview` flow

**`dependency-scan.yml` triggers:** `pull_request` targeting `test` (every PR, regardless of
head branch — same as `quality-gate.yml`). **Permissions:** `contents: read`.

- `pip-audit` / `npm-audit`: guarded on `hashFiles('**/requirements*.txt') != '' ||
  hashFiles('**/pyproject.toml') != ''` and `hashFiles('**/package.json') != ''`
  respectively, same placeholder pattern as the other Phase 3 workflows. Inert until Phase 6
  / Phase 7 add real Python/npm dependency manifests.

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
  hashFiles('frontend/**/Dockerfile') != ''`, same placeholder pattern as the other Phase 3
  workflows. Inert until Phase 8 (Deployment Infrastructure) adds a real Dockerfile; will wire
  versioned image build/push and a staging smoke test at that point.

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
