# Infrastructure

All Docker, deployment, and DevOps configuration. Subfolders: docker/, compose/, nginx/, postgres/, mongodb/, redis/, rabbitmq/, monitoring/, logging/, security/, swarm/, kubernetes/, terraform/, ansible/, scripts/.

## Local Docker Compose stack (Phase 2)

The full local stack — PostgreSQL, MongoDB, Redis, RabbitMQ, Nginx — is defined in
`infrastructure/compose/docker-compose.yml` and driven by the root `Makefile`
(`make up`/`down`/`build`/`restart`/`logs`/`status`/`health`). Every service has a
healthcheck, a persistent named volume, and secrets delivered via Docker secret files, never
plain environment variables. Network isolation is enforced by two Docker networks: `data-net`
(Postgres, MongoDB, Redis, RabbitMQ) and `edge-net` (Nginx) — Nginx has no route to any
database or broker, confirmed by DNS resolution for data-net hostnames failing entirely from
inside the nginx container.

Per-service setup, connection, and backup/restore details:

- [`compose/README.md`](compose/README.md) — stack setup, `.env`/secrets bootstrap
- [`postgres/README.md`](postgres/README.md)
- [`mongodb/README.md`](mongodb/README.md)
- [`redis/README.md`](redis/README.md)
- [`rabbitmq/README.md`](rabbitmq/README.md)
- [`nginx/README.md`](nginx/README.md)

> Status: Phase 2 complete — all five services healthy, `make` targets verified end-to-end,
> persistent volumes and network isolation confirmed. Custom multi-stage Dockerfiles
> (`docker/`) and real upstream wiring in Nginx arrive in Phase 6/7.
