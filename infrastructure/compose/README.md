# Docker Compose

dev/test/prod profiles; backend, frontend, PostgreSQL, MongoDB, Redis, RabbitMQ, Nginx, Prometheus, Grafana, Loki, tracing backend.

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

> Status: Phase 2 — Compose skeleton (networks/volumes/secrets) in place; services added by
> their own Tasks (#50-#54), validated end-to-end by #55.
