# RabbitMQ

Domain events, exchange/queue/routing key structure, Dead Letter Queue, Transactional Outbox support.

## Local Compose service

Defined in `infrastructure/compose/docker-compose.yml`, on `data-net` only. The default
user's password is delivered from the `rabbitmq_password` Docker secret file, never a plain
environment variable in the Compose config. `RABBITMQ_DEFAULT_PASS_FILE` — the official
image's previously-documented file-based convention — is now a hard-rejected deprecated
variable on current `rabbitmq:3-management-alpine` (the container refuses to start and
crash-loops if it is set). The service instead reads the secret file into
`RABBITMQ_DEFAULT_PASS` via a shell command substitution in `command:`, then re-invokes the
image's own `docker-entrypoint.sh rabbitmq-server` — the same secret-file-read pattern already
used for Redis's `requirepass` — which preserves the entrypoint's own root-to-`rabbitmq`-user
demotion, so the server process still ends up running as the non-root `rabbitmq` user.

**Management UI** (local developer convenience only — for inspecting exchanges, queues, and
messages while building Phase 6's publishers/consumers; this port is never exposed beyond
local Compose in any later deployment target):

```text
http://localhost:${RABBITMQ_MANAGEMENT_PORT:-15672}
```

Sign in with `RABBITMQ_DEFAULT_USER` from `.env` and the password from
`infrastructure/compose/secrets/rabbitmq_password.txt` (copied from the `.example` template,
not committed — see `infrastructure/compose/README.md`).

**Exchange/queue conventions**: see `docs/adr/0005-event-topology-and-outbox-design.md` and
`docs/messaging/event-catalog.md` for the exchange/routing-key topology Phase 6 creates on top
of this broker.

> Status: Phase 2 — Compose service defined and healthy; exchanges/queues arrive in Phase 6.
