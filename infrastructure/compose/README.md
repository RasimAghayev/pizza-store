# Docker Compose

backend, frontend, PostgreSQL, MongoDB, Redis, RabbitMQ, Nginx, Prometheus, Grafana, Loki, tracing backend.

## Observability profile

The seven core serving services (`postgres`, `mongodb`, `redis`, `rabbitmq`, `backend`,
`frontend`, `nginx`) carry no `profiles:` key and always start. The Phase 4 monitoring/
logging/tracing/alerting stack (`prometheus`, `alertmanager`, `grafana`, the three exporters,
`loki`, `promtail`, `jaeger`, `otel-collector` — 10 services) is gated behind
`profiles: ["observability"]` (Issue #157), per current Docker Compose guidance: profiles
select which optional services start, they are not an environment-override mechanism (that is
what `docker-compose.prod.yml`, below, is for). `COMPOSE_PROFILES=observability` in
`.env.example` keeps it on by default, so local dev/CI behavior is unchanged from before
profiles existed — a real VPS deployment can override this to run leaner. Confirm either state
with `docker compose -f docker-compose.yml --env-file .env config --services`.

## VPS deployment override

`docker-compose.prod.yml` (Issue #157, ADR 0007) is a merge-only override — never standalone —
for genuinely environment-specific config that `profiles:` is not meant to carry:
TLS-terminating Nginx (`infrastructure/nginx/conf.d.prod/prod.conf`) and a `certbot` service
for Let's Encrypt issuance/renewal. See `docs/deployment/vps.md` for the full deployment
procedure, including the real local stand-in host this Task validated against:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Networks, volumes, secrets

`docker-compose.yml` here defines three networks (`edge-net` for Nginx and, from Phase 6/7,
the backend/frontend; `data-net` for PostgreSQL/MongoDB/Redis/RabbitMQ and, from Phase 6, the
backend — Nginx never joins `data-net`; `monitoring-net`, added in Phase 4, for
Prometheus/Grafana/exporters/Loki/Promtail/the OTel Collector/Jaeger), the named volumes, and
the Docker secrets every service Task reads credentials from. See
`infrastructure/monitoring/README.md` for why Phase 4's three exporters don't all use the
same secret-delivery mechanism, `infrastructure/logging/README.md` for the Loki/Promtail log
pipeline and the Postgres/MongoDB audit-logging baseline (Task #93), and
`infrastructure/tracing/README.md` for the OpenTelemetry Collector + Jaeger tracing skeleton
(Task #94).

Before running `make up`, copy each file in `secrets/` from its `.example` to the real name and
set a real local value:

```sh
for f in secrets/*.txt.example; do cp "$f" "${f%.example}"; done
```

The real `*.txt` files are gitignored; only the `.example` templates are tracked. Also copy the
root `.env.example` to `.env` and adjust values if needed.

> Status: Phase 2 skeleton (networks/volumes/secrets) validated end-to-end by #55; the
> observability profile and VPS prod override are Phase 8 (Issue #157), done.
