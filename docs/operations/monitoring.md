# Monitoring

Operational reference for the metrics, dashboards, logging, and tracing stack added in
Phase 4 (Epic #8). For the per-service implementation detail (credential delivery quirks,
image constraints, exact bugs found while building each piece), see
`infrastructure/monitoring/README.md`, `infrastructure/logging/README.md`, and
`infrastructure/tracing/README.md` — this document is the day-to-day operational view: where
to look, what each surface shows, and the result of re-verifying it against the final,
complete Phase 4 stack (Task #98).

## Where to look

| Surface | URL (local Compose) | What it shows |
|---|---|---|
| Grafana | `http://localhost:${GRAFANA_PORT:-3001}` | Dashboards: `infrastructure-health.json` (scrape-target status, Postgres/MongoDB/Redis connection metrics, RabbitMQ queue depth), `audit-log.json` (live Postgres/MongoDB audit events via the Loki datasource), `business-metrics-placeholder.json` (inert until Phase 10+ adds order/revenue/delivery domain code — Phase 6/7 only built backend/frontend foundations, not business features). Sign in with `admin` and the password in `infrastructure/compose/secrets/grafana_admin_password.txt`. |
| Prometheus | `http://localhost:${PROMETHEUS_PORT:-9090}` | Raw scrape targets (`/targets`), rule evaluation state (`/rules`), ad hoc PromQL (`/graph`). |
| Alertmanager | `http://localhost:${ALERTMANAGER_PORT:-9093}` | Currently firing/resolved alerts and their routing. |
| Jaeger | `http://localhost:${JAEGER_UI_PORT:-16686}` | Trace search/view. Still empty outside manual synthetic-span tests (confirmed during the Issue #167 Phase 9 Gate audit: no `opentelemetry` dependency or instrumentation exists anywhere in `backend/`/`frontend` yet) — no Task has wired real OpenTelemetry instrumentation into Django/Angular, and none is scheduled for a specific phase yet. Storage is in-memory only regardless, so traces are lost on restart (documented limitation, not a bug). |

## What is actually being monitored

Prometheus scrapes five jobs: itself, `postgres` (via `postgres-exporter`), `mongodb` (via
`mongodb-exporter`), `redis` (via `redis-exporter`), and `rabbitmq` (directly, via its own
built-in `rabbitmq_prometheus` plugin — no separate exporter). Loki receives every container's
stdout/stderr via Promtail's Docker service-discovery scrape. Jaeger receives whatever the
OpenTelemetry Collector forwards over OTLP/gRPC on port 4317 or OTLP/HTTP on port 4318.

## Re-verification performed for Phase 4 close-out (2026-11-26, Task #98)

Epic #8's own Acceptance Criteria were re-checked against a single, clean, all-services
bring-up (`make clean && make up`, not each Task's own earlier, narrower validation):

- All 15 Compose services (5 from Phase 2, 10 added across Phase 4) reached `running`, and
  every one of the 10 that carry a Compose healthcheck (`postgres`, `mongodb`, `redis`,
  `rabbitmq`, `nginx`, `prometheus`, `alertmanager`, `grafana`, `postgres-exporter`,
  `jaeger`) reached `healthy`, simultaneously. The remaining 5 (`loki`, `promtail`,
  `mongodb-exporter`, `redis-exporter`, `otel-collector`) have no healthcheck by design —
  scratch/distroless images with no shell to run a `CMD-SHELL` probe against, documented in
  `infrastructure/monitoring/README.md` and `infrastructure/logging/README.md`; their
  functional signal (see below) is what was checked instead of a Docker healthcheck.
- **Metrics**: queried live through Grafana's own datasource-proxy API (not Prometheus
  directly), proving the Grafana -> Prometheus path end to end: `GET
  /api/datasources/proxy/uid/<prometheus-uid>/api/v1/query?query=up` returned `value: 1` for
  all five scrape jobs (`prometheus`, `postgres`, `mongodb`, `redis`, `rabbitmq`) at once.
- **Logs**: a fresh, uniquely-marked `CREATE TABLE <marker>; DROP TABLE <marker>;` was issued
  against the live `postgres` service, and a fresh authenticated `mongosh` connection was
  opened against the live `mongodb` service. After Promtail's scrape interval, both were
  queried back through Grafana's Loki datasource proxy
  (`/api/datasources/proxy/uid/loki/loki/api/v1/query_range`) and found verbatim: the exact
  `LOG: statement: CREATE TABLE <marker>...` line, and a `"msg":"Successfully authenticated"`
  line for the triggering connection. This proves the Grafana -> Loki path live, not just
  Loki's own ingestion.
- **Tracing**: a synthetic OTLP span with a freshly generated random trace/span ID was POSTed
  directly to the collector's HTTP endpoint (`:4318/v1/traces`, HTTP 200), then fetched back
  from Jaeger's query API (`/api/traces/<traceId>`) by that exact trace ID and found present
  with the original span name and service name intact — proving the full
  app -> OTel Collector -> Jaeger forwarding path, not just that the Jaeger UI loads.
- **Alerting**: Alertmanager's `/-/healthy` returned 200 and Prometheus's `/api/v1/rules`
  showed all 3 rule groups / 8 rules loaded (`baseline-availability`,
  `baseline-exporter-health`, `baseline-resource-thresholds`). The actual fire/resolve cycle
  (stopping `redis`, observing `RedisConnectionUnhealthy` fire and clear) was proven once
  already in Task #95 and was not repeated destructively for this close-out — re-confirming
  the rules are loaded and Alertmanager is reachable was judged sufficient re-verification at
  this stage; see `docs/operations/alerting.md` for the original fire/resolve evidence.

The stack was torn down cleanly (`make clean`) after verification — nothing was left running
on the host.

> Status: Phase 4 complete. Metrics (Task #92), logging/audit baseline (Task #93), tracing
> (Task #94), and alerting (Task #95) all independently re-verified together against the
> final merged `test` state, not just individually at each Task's own PR time.
