# Secret management

A current, concrete inventory of every secret that exists in this repository/Compose stack
today: where it lives, which process reads it, and how it gets there. [ADR 0006](../adr/0006-security-architecture-baseline.md)
fixes the *conventions* this inventory follows (Compose `secrets:` files for local
credentials, `.env` for non-sensitive config, GitHub Actions encrypted secrets for CI,
a provider secret manager for a future cloud deployment) — this document does not re-argue
those decisions, it applies them to the real secrets that exist right now.

## Inventory

| Secret | Stored as | Consumed by | Delivery | Committed? |
|---|---|---|---|---|
| `postgres_password` | Compose secret file: `infrastructure/compose/secrets/postgres_password.txt` | `postgres` service; `postgres-exporter` service | File mount at `/run/secrets/postgres_password`. `postgres` reads it via `POSTGRES_PASSWORD_FILE`; `postgres-exporter`'s entrypoint `cat`s it into the `DATA_SOURCE_NAME` connection string before exec'ing the exporter binary. | `.example` template only |
| `mongo_root_password` | Compose secret file: `infrastructure/compose/secrets/mongo_root_password.txt` | `mongodb` service | File mount at `/run/secrets/mongo_root_password`, read via `MONGO_INITDB_ROOT_PASSWORD_FILE`. | `.example` template only |
| `mongodb_exporter_password` | Compose secret file: `infrastructure/compose/secrets/mongodb_exporter_password.txt` | `mongodb` service only (not `mongodb-exporter`) | File mount at `/run/secrets/mongodb_exporter_password`, read by `infrastructure/mongodb/init/01-create-exporter-user.sh` during the unauthenticated init phase to create the least-privilege `mongodb_exporter` monitoring user. Its plaintext value must match `MONGODB_EXPORTER_PASSWORD` below by hand — the two exist because `mongodb` can take a secrets file but the `mongodb-exporter` image cannot. | `.example` template only |
| `MONGODB_EXPORTER_PASSWORD` | `.env` variable (documented exception to the file-secret convention) | `mongodb-exporter` service | Compose variable interpolation into the exporter's `--mongodb.uri` CLI argument — `percona/mongodb_exporter` is a scratch-based single-binary image with no shell and no password-file flag, so a file mount is not possible. | `.env.example` placeholder only; real value lives in gitignored `.env` |
| `redis_password` | Compose secret file: `infrastructure/compose/secrets/redis_password.txt` | `redis` service | File mount at `/run/secrets/redis_password`; the service's shell command `cat`s it into `redis-server --requirepass`. | `.example` template only |
| `redis_exporter_password` | Compose secret file: `infrastructure/compose/secrets/redis_exporter_password.txt` | `redis-exporter` service | File mount, passed via `-redis.password-file`. Holds the *same* password as `redis_password.txt`, JSON-wrapped (`{"redis://redis:6379": "<password>"}`) because that is the shape `-redis.password-file` expects — the two files must be kept in sync by hand. | `.example` template only |
| `rabbitmq_password` | Compose secret file: `infrastructure/compose/secrets/rabbitmq_password.txt` | `rabbitmq` service | File mount at `/run/secrets/rabbitmq_password`; the service's shell command exports it as `RABBITMQ_DEFAULT_PASS`. | `.example` template only |
| `grafana_admin_password` | Compose secret file: `infrastructure/compose/secrets/grafana_admin_password.txt` | `grafana` service | File mount, read via `GF_SECURITY_ADMIN_PASSWORD__FILE`. | `.example` template only |
| `backup_encryption_key` | Compose secret file: `infrastructure/compose/secrets/backup_encryption_key.txt` | `scripts/backup-postgres.sh`, `scripts/backup-mongodb.sh`, `scripts/restore-postgres.sh`, `scripts/restore-mongodb.sh` | Declared in the Compose file's top-level `secrets:` block for inventory consistency, but **not mounted into any service** — `gpg` runs on the host (or the CI runner), not inside the `postgres`/`mongodb` containers, so each script reads the file directly from its path on disk. Passphrase for `gpg --symmetric --cipher-algo AES256` backup-archive encryption/decryption; see [the backup/restore runbook](../runbooks/backup-restore.md). | `.example` template only |
| `django_secret_key` | Compose secret file: `infrastructure/compose/secrets/django_secret_key.txt` | `backend` service | File mount at `/run/secrets/django_secret_key`, read by `backend/config/settings.py`'s `_read_secret()` helper into `SECRET_KEY`. Falls back to a hardcoded insecure default when the file is absent (e.g. a one-off `manage.py` command run outside Compose). | `.example` template only |
| `jwt_private_key` | Compose secret file: `infrastructure/compose/secrets/jwt_private_key.txt` | `backend` service | File mount at `/run/secrets/jwt_private_key`; generated via `scripts/generate-jwt-keypair.py` (`make generate-jwt-keypair`). RS256 PEM private key read by `backend/apps/identity/services/token_service.py` to sign access tokens; the public key is derived in-process (`private_key.public_key()`), never stored as a second secret. Falls back to an ephemeral, process-local keypair (generated once at import time, never persisted) when the file is absent, so lightweight test/CI runs outside Compose don't need a real key — see [ADR 0006](../adr/0006-security-architecture-baseline.md). | `.example` template only (a second, throwaway keypair — never used outside CI/local placeholder runs) |
| `GITHUB_TOKEN` | GitHub Actions ambient token | `secret-scan.yml` (gitleaks step) | Automatically provisioned by GitHub Actions for every workflow run; not a repository secret anyone configured or can rotate independently. Scoped read-only (`permissions: contents: read`) in this workflow. | N/A — never stored anywhere, ambient per run |

No other `secrets.*` reference exists in `.github/workflows/*.yml` as of this writing (checked
against every workflow file, not from memory).

### CI-only ephemeral values (not secrets requiring management)

`backup-restore-test.yml`, `integration-validation.yml`, and `production-acceptance.yml` each
copy `.env.example` to `.env` and every `infrastructure/compose/secrets/*.txt.example` to its
real counterpart at the start of the job, so the Compose stack has *something* to read. These
are the literal placeholder values from the `.example` files (e.g. `changeme-local-dev-only`),
not generated or randomized, scoped only to that ephemeral runner's filesystem, and discarded
when the job ends. They are not part of the secret inventory above because they never protect
anything real — no production or shared system trusts them.

## Access control

- **Compose secret files**: a container only sees a secret if its service declares that
  secret under `secrets:` in `infrastructure/compose/docker-compose.yml` — Docker's own
  file-permission mechanism (`/run/secrets/<name>`, mode `0444`, root-owned) inside the
  container is what enforces this, not anything this repository adds on top. `mongodb-exporter`,
  for example, cannot read `mongo_root_password` because its service block never lists it.
- **The real `.txt` files on disk**: never committed (`infrastructure/compose/secrets/*.txt`
  is gitignored; only the `*.txt.example` templates are tracked — see `.gitignore`). Access to
  the real files is controlled by host filesystem permissions, which this repository does not
  and cannot govern.
- **`.env`**: same pattern — `.env` is gitignored, `.env.example` is tracked with placeholder
  values only (see `.gitignore`).
- **GitHub Actions secrets**: `GITHUB_TOKEN` is scoped per-workflow via the `permissions:`
  block (read-only in `secret-scan.yml`); no other repository or environment secret is
  currently configured.
- **Complementary, account-level layers** (not managed by this repository, listed here only so
  this document is a complete picture): the account-wide GitGuardian app and GitHub's native
  secret scanning + push protection (enabled under this repository's Settings → Code security
  and analysis) both scan for secrets reaching a commit. `secret-scan.yml`'s gitleaks job is a
  third, repo-owned layer alongside them, not a replacement for either.

## Rotation

There is currently no automated rotation for any secret in the table above — correct and
honest for this phase, not a gap being papered over. Rotating any of these today means: generate
a new value, write it into the relevant `.txt`/`.env` file, and restart the affected
service(s) (`docker compose up -d --force-recreate <service>` for secrets-file changes,
since Compose does not hot-reload a mounted secret file). For the two synchronized pairs
(`mongodb_exporter_password.txt` / `MONGODB_EXPORTER_PASSWORD`, and `redis_password.txt` /
`redis_exporter_password.txt`), both sides of the pair must be updated together or the
exporter will fail to authenticate.

Automated rotation is deliberately deferred to a future Task once a real deployment target
([ADR 0007](../adr/0007-deployment-target-priority.md)) is live and a provider secret manager
(per ADR 0006's "future cloud deployment" plan) is actually in place to rotate against —
inventing a rotation mechanism for purely local Compose secrets ahead of that need would be
speculative infrastructure this phase has no use for.
