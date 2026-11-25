# Redis

Cache, session, rate limiting, OTP, courier's last known coordinates, order status cache. Not a source of truth.

## Local Compose service

Defined in `infrastructure/compose/docker-compose.yml`, on `data-net` only. The official
`redis` image has no `_FILE`-suffix convention for `requirepass` (unlike Postgres/Mongo), so
the password is read from the Docker secret file at container start via shell command
substitution. `requirepass` is always set — Redis is never started without authentication,
even for local dev. The image already runs as its non-root `redis` user by default.

`--appendonly yes` is enabled for local-dev convenience only, so cached state survives a
container restart without re-population. This does not change Redis's role per ADR 0002 and
`docs/database/redis-caching-and-ttl-policy.md`: it is never the source of truth, and
persistence here is a dev convenience, not a durability guarantee.

**Connect locally** (after `make up`):

```sh
redis-cli -a <password> -p ${REDIS_PORT:-6379}
```

The password is read from `infrastructure/compose/secrets/redis_password.txt` (copied from the
`.example` template, not committed — see `infrastructure/compose/README.md`).

> Status: Phase 2 — Compose service defined, authenticated, and healthy; key patterns arrive in Phase 6.
