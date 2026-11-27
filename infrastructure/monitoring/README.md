# Monitoring

Prometheus, Grafana dashboards, key business and system metrics.

## Local Compose services

Defined in `infrastructure/compose/docker-compose.yml` (Task #92), on `monitoring-net`:

- **Prometheus** (`prometheus/prometheus.yml`) scrapes itself plus `postgres-exporter`,
  `mongodb-exporter`, `redis-exporter`, and `rabbitmq` directly (RabbitMQ serves its own
  `/metrics` via the `rabbitmq_prometheus` plugin, enabled at container start — no separate
  exporter needed).
- **Grafana** is provisioned (`grafana/provisioning/`) with the Prometheus datasource and two
  dashboards (`grafana/dashboards/`): `infrastructure-health.json` (real, populated today —
  scrape-target status, Postgres connection count, MongoDB connection count, Redis connected
  clients, RabbitMQ queue depth) and `business-metrics-placeholder.json` (inert until
  Phase 6/7 add application-level metrics).

```text
http://localhost:${GRAFANA_PORT:-3001}
```

Sign in with `admin` and the password from
`infrastructure/compose/secrets/grafana_admin_password.txt`.

**Credential delivery, three different ways** (each image's own constraints decided this,
not a style preference — see `docs/security/secret-management.md` for the full inventory):

- `postgres-exporter` has a shell (busybox `sh`), so its `entrypoint` is overridden to read
  the `postgres_password` Compose secret file and build `DATA_SOURCE_NAME` before exec'ing
  the real binary — same pattern as `redis`/`rabbitmq`'s own commands in the parent Compose
  file.
- `redis-exporter` is a shell-less, scratch-based single binary, but natively supports
  `-redis.password-file` — which, discovered empirically while validating this Task, expects
  a JSON object keyed by address (`{"redis://host:port": "password"}`), not a raw password
  string. `redis_exporter_password.txt` holds the same password as `redis_password.txt` in
  that JSON shape; the two must be kept in sync by hand.
- `mongodb-exporter` is also shell-less and has no password-file flag at all, so its
  credential is delivered via `MONGODB_EXPORTER_PASSWORD` (`.env`, gitignored, never
  committed) — a documented, narrow exception to the file-secret convention — authenticating
  as a dedicated, least-privilege monitoring user (`mongodb_exporter`, `clusterMonitor` +
  `read` on `local`, never the Mongo root user) created by
  `infrastructure/mongodb/init/01-create-exporter-user.sh`.

**A real, previously-undetected bug found while validating this Task**: `core.autocrlf=true`
on Windows checkouts silently converts every tracked `*.txt.example` secret template to
CRLF, and nothing overrode that — so every `$(cat /run/secrets/...)` read in this file has
carried a trailing `\r` since Phase 2. It stayed invisible because the only two consumers
(`redis`, `rabbitmq`) read the same tainted file on both the server and the healthcheck
side, so they stayed self-consistent. It surfaced the moment a *second*, independently
written file needed to match the same password (`redis_exporter_password.txt`). Fixed at
the root with `.gitattributes` (`text eol=lf` on the example templates and all `*.sh`
files) and defensively with `tr -d '\r'` at every secret-file read site in this Compose
file, not just the one that first exposed it.

**No healthcheck** on `mongodb-exporter`/`redis-exporter`: both are scratch-based images with
no shell, `wget`, or `curl` to run a `CMD-SHELL` probe against. Prometheus's own `up{job=...}`
scrape result is the real health signal for these two.

## Logging

Grafana's Loki datasource and the `audit-log.json` dashboard are provisioned here too, but the
Loki/Promtail services themselves and the audit-logging baseline are documented in
`infrastructure/logging/README.md` (Task #93).

## Tracing

The OpenTelemetry Collector and Jaeger services, and the synthetic-span validation proving
the pipeline, are documented in `infrastructure/tracing/README.md` (Task #94).

## Alerting

Defined in `infrastructure/compose/docker-compose.yml` (Task #95):

- **Prometheus** evaluates `prometheus/alert-rules.yml` (loaded via `rule_files:`) and routes
  firing alerts to **Alertmanager** (`alerting.alertmanagers`, both in `prometheus.yml`).
- Eight baseline rules across three groups:
  - `baseline-availability`: `InstanceDown` (`up == 0` for 1m on any scrape target).
  - `baseline-exporter-health`: `PostgresConnectionUnhealthy`/`MongoDBConnectionUnhealthy`/
    `RedisConnectionUnhealthy` on each exporter's own `pg_up`/`mongodb_up`/`redis_up` gauge —
    distinct from `up{job=...}`, which only confirms the exporter *process* answered the
    scrape, not that its connection to the database it monitors is healthy. RabbitMQ has no
    separate exporter (scraped directly), so there's no equivalent gauge to alert on there.
  - `baseline-resource-thresholds`: `PostgresConnectionsNearMax` (connections > 80% of
    `pg_settings_max_connections`), `RedisMemoryNearContainerLimit` (used memory > 200MiB —
    80% of the `redis` service's own `mem_limit: 256m`; `redis.conf` sets no `--maxmemory`
    here, confirmed empirically via `redis_memory_max_bytes` reporting `0`, so the Compose
    `mem_limit` is the real constraint in force, not Redis's own), `RabbitMQQueueDepthHigh`
    (total queue depth > 1000), `MongoDBConnectionsNearMax` (current connections > 80% of
    current+available capacity).
- **Alertmanager** (`alertmanager/alertmanager.yml`) routes every alert to a single receiver
  with **no integrations configured at all** — not a `null`-type receiver (Alertmanager has
  no such type), just a named receiver with zero notification channels, so every routed alert
  is accepted and visible in Alertmanager's own UI/API without any outbound delivery attempt
  or failure. **No real Slack/email/PagerDuty channel is wired up** — that's an
  account-level integration decision explicitly out of this Task's scope until an actual
  on-call process exists to receive it. This is a documented, deliberate gap.

```text
http://localhost:${ALERTMANAGER_PORT:-9093}
```

**Real validation (not a configuration review)**: with the full stack up, `redis` was
stopped via Compose. `RedisConnectionUnhealthy{job="redis-exporter"}` fired in Prometheus's
`/api/v1/alerts` after the rule's 1-minute `for` duration and was confirmed received by
Alertmanager's `/api/v2/alerts` within its `group_wait` — not `InstanceDown`, since nothing
scrapes a `redis` job directly: only `redis-exporter` is a scrape target, and that process
keeps answering Prometheus throughout (`up{job="redis-exporter"}` stays `1`), it just reports
`redis_up 0` once its own connection to the database fails. This is the exporter-health vs.
`up{job=...}` distinction above, proven live rather than asserted. `redis` was then restarted,
and the alert was confirmed resolved (gone from both APIs) on the next evaluation cycle.

> Status: Phase 4 complete (Epic #8 closed, Task #98). Metrics stack (Prometheus, Grafana,
> exporters) implemented and validated against a real, clean `make up` run: all 9 Compose
> services healthy (or, for the two shell-less exporters, confirmed `up` via Prometheus's own
> scrape result), all 5 Prometheus scrape targets `up`, and real metric values (not just
> connectivity) confirmed for every target through a live Grafana-proxied query.
> Logging/audit baseline added by Task #93; tracing skeleton added by Task #94; alerting
> rules + Alertmanager added by Task #95, proven with a real stop/restart alert
> fire-and-resolve cycle; backup/restore added by Task #96; secret management documented by
> Task #97. All of it re-verified together, against the full 15-service stack at once, for
> Phase 4 close-out — see `docs/operations/monitoring.md`.
