# PostgreSQL

Source of truth: users, customers, orders, payments, restaurants, inventory transactions. Init scripts and migration support.

## Local Compose service

Defined in `infrastructure/compose/docker-compose.yml`, on `data-net` only. The official
`postgres` image already runs the server process as its non-root `postgres` user by default —
no extra `user:` directive is needed.

**Connect locally** (after `make up`):

```sh
psql -h localhost -p ${POSTGRES_PORT:-5432} -U ${POSTGRES_USER:-pizza_store} -d ${POSTGRES_DB:-pizza_store}
```

The password is read by the container from `infrastructure/compose/secrets/postgres_password.txt`
(copied from the `.example` template, not committed — see `infrastructure/compose/README.md`).

**Init scripts**: `infrastructure/postgres/init/` is mounted to `/docker-entrypoint-initdb.d/`
and runs once, only against a brand-new (empty) data volume. Empty for now; Phase 6 adds
bootstrap scripts here if a one-time setup step becomes necessary.

**Backup / restore**:

```sh
# Backup
docker compose -f infrastructure/compose/docker-compose.yml exec -T postgres \
  pg_dump -U ${POSTGRES_USER:-pizza_store} ${POSTGRES_DB:-pizza_store} > backup.sql

# Restore
docker compose -f infrastructure/compose/docker-compose.yml exec -T postgres \
  psql -U ${POSTGRES_USER:-pizza_store} -d ${POSTGRES_DB:-pizza_store} < backup.sql
```

> Status: Phase 2 — Compose service defined and healthy; schema/migrations arrive in Phase 6.
