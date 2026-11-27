# Logging

Centralized logging (Loki), log format and retention policy.

## Local Compose services

Defined in `infrastructure/compose/docker-compose.yml` (Task #93), on `monitoring-net`:

- **Loki** (`loki-config.yml`) stores logs with a filesystem storage backend only — no
  external object store (S3/GCS) is provisioned for this stack. Chunks and the TSDB index
  live under the `loki-data` named volume.
- **Promtail** (`promtail-config.yml`) discovers every running container via Docker service
  discovery (a read-only mount of `/var/run/docker.sock`, used only to list containers and
  their labels — never to create/start/stop anything) and tails each container's
  `json-file`-driver log files (read-only mount of `/var/lib/docker/containers`). It relabels
  Docker Compose's own `com.docker.compose.service` container label (the exact service key
  from `docker-compose.yml`, e.g. `postgres`, `mongodb`) into a `container` label and pushes
  to Loki — a real finding from validating this Task: the generated Docker container *name*
  (`compose-postgres-1`) is not the same string, and the audit-log panel's
  `{container=~"postgres|mongodb"}` query silently returned zero results until the relabel
  source was switched to the compose service label.
- Grafana's **Loki** datasource (`grafana/provisioning/datasources/loki.yml`, `uid: loki`) and
  the **`audit-log.json`** dashboard (Explore-able via the same datasource) are provisioned
  alongside the Prometheus ones added by Task #92.

## Baseline audit logging

Epic #8 requires "a baseline audit log mechanism exists" without building the future
application-level `audit` domain module (that's ADR 0002/0004's Phase 6/11 scope). This Task
satisfies it at the infrastructure level, shipped through the same Loki/Promtail pipeline as
every other container's logs:

- **PostgreSQL**: `command: ["postgres", "-c", "log_connections=on", "-c",
  "log_disconnections=on", "-c", "log_statement=ddl"]` on the `postgres` service — chosen over
  a mounted `postgresql.audit.conf` because it keeps the one audit-relevant setting visible
  directly in Compose instead of a second file to cross-reference.
- **MongoDB**: `command: ["--auth", "--setParameter",
  "logComponentVerbosity={\"accessControl\":{\"verbosity\":1}}"]` on the `mongodb` service.
  `mongo:7`'s stock image has no Percona-style `auditLog`; `accessControl` verbosity is the
  available substitute. `--auth` is the more consequential half of this change: before this
  Task, `MONGO_INITDB_ROOT_USERNAME`/`PASSWORD` created a root user but nothing actually
  enforced authentication on client connections — `--auth` closes that gap. Verified by a real
  test that this list-form `command:` (it starts with `-`, so `mongo:7`'s
  `docker-entrypoint.sh` prepends `mongod` itself) does not conflict with the
  `MONGO_INITDB_ROOT_*` first-run initialization or with
  `infrastructure/mongodb/init/01-create-exporter-user.sh` (that script runs during the
  entrypoint's unauthenticated init phase, before `--auth` is enforced for normal client
  connections, so it is unaffected).

The `audit-log.json` dashboard's single Loki panel filters `{container=~"postgres|mongodb"}`
for connection/disconnection, DDL, and MongoDB access-control authentication keywords (the
latter matches mongod's actual log vocabulary — `successfully authenticated`,
`connection accepted/ended`, `checking authorization` — rather than the literal string
`accessControl`, which never appears verbatim in a log line).

## Known gap

Retention/rotation beyond Loki's own defaults is explicitly out of scope for this Task —
a known gap deferred to a future dedicated retention-policy Task once real usage patterns
inform one (see `docs/runbooks/incident-response.md`); not something
`docs/security/secret-management.md` (Task #97) covers, despite an earlier, inaccurate
cross-reference to it here.

> Status: Phase 4 complete (Epic #8 closed, Task #98). Loki/Promtail log aggregation and the
> Postgres/MongoDB audit-logging baseline implemented and validated against a real, clean
> `make up` run: a real `psql` DDL statement and a real `mongosh` connection (authenticated
> and, to prove enforcement, unauthenticated-and-rejected) both appear in the
> `audit-log.json` Grafana panel, and every other container's logs are browsable in
> Grafana's Explore view. Re-verified again at Phase 4 close-out against the full combined
> stack (`docs/operations/monitoring.md`).
