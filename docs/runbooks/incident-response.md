# Incident response

A baseline "what to check first" runbook for the local Compose stack, using the Grafana
dashboards and Alertmanager added in Phase 4 (Epic #8). There is no production deployment yet
(ADR 0007 fixes the future target) and no real on-call rotation or paging integration — this
runbook covers triage of the observability stack itself, which is all that exists to triage
today. It will grow a deployment-specific section once Phase 8/9 add a real environment.

## 1. Check Alertmanager first

`http://localhost:${ALERTMANAGER_PORT:-9093}` — any currently firing alert and its labels
(`job`, `instance`, `alertname`) point at which service is unhealthy. See
`docs/operations/alerting.md` for what each of the 8 baseline rules means and when it fires.

## 2. Confirm the affected service's own state

```text
make status   # docker compose ps — State/Health for every service
make logs     # follow logs for everything; or:
docker compose -f infrastructure/compose/docker-compose.yml --env-file .env logs -f <service>
```

A service with no Compose healthcheck (`loki`, `promtail`, `mongodb-exporter`,
`redis-exporter`, `otel-collector` — scratch/distroless images, no shell to probe with) will
never show `unhealthy` even when broken; for those, check Prometheus's own `up{job=...}` /
`<service>_up` gauges (Grafana's `infrastructure-health.json` dashboard) instead of `docker
compose ps`.

## 3. Cross-check metrics, logs, and traces together

- **Metrics**: Grafana's `infrastructure-health.json` dashboard, or raw PromQL at
  `http://localhost:${PROMETHEUS_PORT:-9090}/graph`.
- **Logs**: Grafana's Explore view against the Loki datasource, or the `audit-log.json`
  dashboard for Postgres/MongoDB connection and DDL/auth events specifically.
- **Traces**: `http://localhost:${JAEGER_UI_PORT:-16686}` — empty until a real application
  exists to emit spans (Phase 6/7); useful once request-level tracing is in place.

Correlate by timestamp and container name (Promtail labels every log line with the Compose
service name, e.g. `container="postgres"`, not the generated container name like
`compose-postgres-1`).

## 4. Database-specific first checks

- **Postgres down/unreachable**: check `postgres`'s own health
  (`docker compose exec postgres pg_isready`), then `postgres-exporter`'s `/metrics` for
  `pg_up`. Connection-count pressure shows as `PostgresConnectionsNearMax`.
- **MongoDB down/unreachable**: `docker compose exec mongodb mongosh --eval
  "db.adminCommand('ping')"` (requires `--auth` credentials since Task #93 — anonymous
  connections are rejected by design). `mongodb-exporter` has no healthcheck; rely on
  Prometheus's `mongodb_up`.
- **Redis down/unreachable**: `RedisConnectionUnhealthy` (connection-level) is distinct from
  `RedisMemoryNearContainerLimit` (the container's own 256m `mem_limit`, not a Redis
  `maxmemory` setting — confirmed empirically that Redis itself enforces no memory cap here).
- **RabbitMQ**: scraped directly via its own `rabbitmq_prometheus` plugin (no separate
  exporter); `RabbitMQQueueDepthHigh` signals consumer lag or a stuck consumer, not a broker
  outage by itself.

## 5. Data recovery

If data loss or corruption is suspected, see `docs/runbooks/backup-restore.md` for the
real, tested backup/restore procedure — restore always targets a disposable container, never
the live service, so a restore attempt itself cannot make an incident worse.

## 6. Known gaps in this baseline

- No real notification channel (Slack/email/PagerDuty) is wired to Alertmanager — alerts are
  only visible by someone actively checking Alertmanager/Grafana, not pushed to anyone. See
  `docs/operations/alerting.md`.
- No log retention/rotation policy beyond Loki's own defaults exists yet — deferred to a
  future dedicated Task once real usage patterns inform a retention policy, not tracked under
  any currently open Issue.
- Jaeger's trace storage is in-memory only — a restart loses trace history. Acceptable until
  a real application and real retention requirements exist (Phase 6/7).

> Status: Phase 4 — baseline incident-response triage procedure, covering only the
> observability stack itself (no production deployment exists yet to have incidents in).
