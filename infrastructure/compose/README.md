# Docker Compose

dev/test/prod profiles; backend, frontend, PostgreSQL, MongoDB, Redis, RabbitMQ, Nginx, Prometheus, Grafana, Loki, tracing backend.

`docker-compose.yml` here defines two networks (`edge-net` for Nginx and, from Phase 6/7, the
backend/frontend; `data-net` for PostgreSQL/MongoDB/Redis/RabbitMQ and, from Phase 6, the
backend — Nginx never joins `data-net`), the four named volumes, and the four Docker secrets
every service Task reads credentials from.

Before running `make up`, copy each file in `secrets/` from its `.example` to the real name and
set a real local value:

```sh
for f in secrets/*.txt.example; do cp "$f" "${f%.example}"; done
```

The real `*.txt` files are gitignored; only the `.example` templates are tracked. Also copy the
root `.env.example` to `.env` and adjust values if needed.

> Status: Phase 2 — Compose skeleton (networks/volumes/secrets) in place; services added by
> their own Tasks (#50-#54), validated end-to-end by #55.
