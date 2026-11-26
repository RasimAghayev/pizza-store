# Alerting

Operational reference for the Prometheus alert rules and Alertmanager added in Task #95.
See `infrastructure/monitoring/README.md` for the original implementation detail and the
real stop/restart proof performed at that Task's own validation time; this document is the
day-to-day reference plus the Phase 4 close-out (Task #98) re-verification.

## Rule groups

Defined in `infrastructure/monitoring/prometheus/alert-rules.yml`, loaded by Prometheus via
`rule_files:`:

| Group | Rule | Fires when |
|---|---|---|
| `baseline-availability` | `InstanceDown` | Any scrape target's `up == 0` for 1 minute |
| `baseline-exporter-health` | `PostgresConnectionUnhealthy` | `postgres-exporter`'s own `pg_up` gauge reports the exporter can't reach Postgres (distinct from `up{job="postgres"}`, which only confirms the exporter process answered the scrape) |
| `baseline-exporter-health` | `MongoDBConnectionUnhealthy` | `mongodb-exporter`'s `mongodb_up` gauge reports it can't reach MongoDB |
| `baseline-exporter-health` | `RedisConnectionUnhealthy` | `redis-exporter`'s `redis_up` gauge reports it can't reach Redis |
| `baseline-resource-thresholds` | `PostgresConnectionsNearMax` | Current connections > 80% of `pg_settings_max_connections` |
| `baseline-resource-thresholds` | `MongoDBConnectionsNearMax` | Current connections > 80% of current+available capacity |
| `baseline-resource-thresholds` | `RedisMemoryNearContainerLimit` | Used memory > 200MiB (80% of the `redis` service's `mem_limit: 256m` — Redis itself sets no `--maxmemory`, confirmed empirically, so the Compose container limit is the real constraint) |
| `baseline-resource-thresholds` | `RabbitMQQueueDepthHigh` | Total queue depth across all queues > 1000 |

RabbitMQ has no separate exporter (Prometheus scrapes it directly via its own
`rabbitmq_prometheus` plugin), so there is no equivalent connection-health gauge to alert on
for it beyond `InstanceDown`.

## Routing

Prometheus routes every firing alert to Alertmanager (`alerting.alertmanagers` in
`prometheus.yml`, targeting `alertmanager:9093`). Alertmanager
(`infrastructure/monitoring/alertmanager/alertmanager.yml`) routes every alert to a single
receiver with **zero notification integrations configured** — not Alertmanager's `null` type
(it has none), just a receiver with no outbound channel, so every alert is accepted and
visible in Alertmanager's own UI/API with no delivery attempt or failure.

**No real Slack/email/PagerDuty channel is wired up.** This is a deliberate, documented gap:
wiring a real channel is an account-level integration decision that has no real on-call
process to receive it yet, and is out of scope until one exists.

## Original validation (Task #95, real stop/restart test)

With the full stack up, `redis` was stopped via Compose.
`RedisConnectionUnhealthy{job="redis-exporter"}` fired in Prometheus's `/api/v1/alerts`
after the rule's 1-minute `for` duration and was confirmed received by Alertmanager's
`/api/v2/alerts` within `group_wait` — not `InstanceDown`, since `redis-exporter` (the actual
scrape target) kept answering Prometheus throughout; only its own `redis_up` gauge dropped to
0. `redis` was restarted and the alert was confirmed resolved (gone from both APIs) on the
next evaluation cycle.

## Phase 4 close-out re-verification (2026-11-26, Task #98)

Against a fresh, clean `make up` of the complete 15-service stack: Alertmanager's
`/-/healthy` returned HTTP 200, and Prometheus's `/api/v1/rules` showed all 3 rule groups and
all 8 rules loaded and in `ok` evaluation state. The destructive stop/restart test above was
not repeated for this close-out (it was already proven once, real, at Task #95) — this
re-verification confirms the rules and routing survived unchanged into the final merged
`test` state, not that alerting works at all (already established).

> Status: Phase 4 complete. Alert rules and Alertmanager routing verified both at
> implementation time (real fire/resolve cycle) and again at Phase 4 close-out (rules loaded,
> Alertmanager reachable, against the full combined stack).
