# Docker Swarm Deployment

> Status: Phase 8 (Issue #158) — `infrastructure/swarm/docker-stack.yml` validated end to end
> on a real local single-node Swarm. Per ADR 0007, Swarm was built and validated before
> Kubernetes (Issue #159) so translation issues get solved once here and carry forward.

## Prerequisites

- Docker Engine 29.x+ with Swarm mode support (bundled with every current Docker Engine/
  Docker Desktop release — no separate installation).
- `infrastructure/compose/.env` populated (same file the local Compose stack already uses)
  and `infrastructure/compose/secrets/*.txt` populated (same secret files the local Compose
  stack already uses — this stack file references them directly via relative paths, there is
  no separate Swarm-only secret-file set to maintain).
- `backend`/`frontend` images built locally: `docker compose -f
  infrastructure/compose/docker-compose.yml build backend frontend`. Swarm never builds a
  `build:` section — only pre-built images.
- For a real multi-node cluster (not required for the single-node validation below): a
  container registry reachable by every node, since Swarm does not share one node's local
  image cache with the others.

## Environment

`${VAR}` placeholders in `docker-stack.yml` are substituted from the **invoking shell's own
exported environment**, not auto-loaded from a `.env` file the way `docker compose` does —
confirmed by a real failure during this validation (see Troubleshooting). Export the existing
Compose `.env` before deploying:

```sh
set -a; source infrastructure/compose/.env; set +a
docker stack deploy -c infrastructure/swarm/docker-stack.yml pizza-store
```

## Secrets

Every secret already defined for the local Compose stack (`postgres_password`,
`mongo_root_password`, `redis_password`, `rabbitmq_password`, `grafana_admin_password`,
`mongodb_exporter_password`, `redis_exporter_password`, `django_secret_key`,
`jwt_private_key`) is declared in `docker-stack.yml`'s top-level `secrets:` with a `file:`
source pointing at `../compose/secrets/*.txt` — `docker stack deploy` creates each Swarm
secret object from that file automatically on first deploy, the same convenience `docker
compose` offers locally. No separate secret material exists for Swarm.

## Networking

Three overlay networks mirror the Compose stack's bridge networks exactly:
`edge-net` (Nginx only), `data-net` (every database/broker plus `backend`), `monitoring-net`
(every observability component). Overlay networks route between nodes natively; on the
single-node validation below they behave identically to the bridge equivalents, but the
driver change is what makes a real multi-node cluster possible without any other config
change.

**Verified isolation**: `nginx` (edge-net only) cannot even resolve `postgres` by name —
`wget http://postgres:5432` from inside the `nginx` task failed with `bad address
'postgres:5432'`, a DNS-level failure proving `nginx`'s task has no route to `data-net` at
all, not just a blocked connection. `backend` (both `edge-net` and `data-net`) reaches
`postgres` normally (proven indirectly: Prometheus's `postgres-exporter` target, itself on
`data-net`, reported `up` throughout).

## Database setup

No database-specific Swarm steps beyond what the Compose stack already does — `postgres`/
`mongodb`/`redis`/`rabbitmq` use the exact same images, init command flags, and healthchecks
as `infrastructure/compose/docker-compose.yml`. Each is constrained to `replicas: 1` and
pinned to one node via `placement.constraints: [node.labels.pizza-store.data == true]`,
labeled once before deploying:

```sh
docker node update --label-add pizza-store.data=true <node-id>
```

This is a real, named limitation, not an oversight: Swarm's default `local` volume driver has
no cross-node data sharing, so a second replica of any stateful service would get its own
independent, inconsistent volume rather than joining the first. A real multi-node cluster
needs a network-attached volume driver (e.g. a cloud block-storage plugin) to lift this
constraint; it is not solved by this Task.

## Backup/Restore

Unchanged from the existing `docs/runbooks/backup-restore.md` procedure — `scripts/
backup-postgres.sh`/`backup-mongodb.sh` connect via `docker compose exec`, not anything
Swarm-specific. Running them against a Swarm-deployed stack only requires pointing at the
right container (`docker ps --filter label=com.docker.swarm.service.name=pizza-store_postgres`
instead of a Compose service name) — the dump/restore mechanism itself does not change.

## SSL

Out of scope for this Task — TLS termination is the VPS deployment's responsibility (Issue
#157, ADR 0007). A real multi-node Swarm cluster would terminate TLS the same way the VPS
target does: Nginx (replicated here, same as this stack file already does) fronting the
cluster with a certificate, or an external load balancer terminating TLS ahead of the Swarm
routing mesh.

## Reverse proxy

`nginx` is replicated at 2 and published via Swarm's **ingress routing mesh** (the default
publish mode) — every node in the cluster accepts traffic on the published port and routes it
to a healthy `nginx` task via Swarm's internal load balancer, not just the node a given task
happens to run on. Verified: `curl http://localhost/healthz` and `curl
http://localhost/api/schema/` both returned `200` throughout the validation, including during
the rolling update below.

## Monitoring

Unchanged from Phase 4: `prometheus` scrapes `postgres-exporter`/`redis-exporter`/
`mongodb-exporter`/`rabbitmq` (built-in `rabbitmq_prometheus` plugin)/itself over
`monitoring-net`. Verified with a real query against the deployed stack:
`GET /api/v1/query?query=up` returned `"1"` for all five targets
(`prometheus`, `postgres`, `rabbitmq`, `redis`, `mongodb`) with no translation-specific gap.

## Logging

`promtail` is deployed with `deploy.mode: global` (one task per Swarm node) rather than
`replicated`, the same pattern as a Kubernetes DaemonSet — it reads the **local** Docker
daemon socket and container-log directory of whichever node it runs on, so a replicated
deployment pinned to one node would miss every other node's container logs entirely on a
real multi-node cluster. On this single-node validation, `global` mode converged to exactly
one task, identical in effect to `replicated: 1`.

## Scaling

Stateless/edge services (`backend`, `frontend`, `nginx`) are replicated at 2 and can be
scaled further with `docker service scale pizza-store_backend=<n>` — the routing mesh and
Prometheus service-discovery both adapt automatically, no config change needed. Stateful
services are intentionally not horizontally scaled (see Database setup).

## Rollback

`update_config.failure_action: rollback` is set on every replicated stateless service
(`backend`, `frontend`, `nginx`) — if a rolling update's health checks fail, Swarm
automatically reverts to the previous task definition. Not exercised in this validation (the
real rolling update below succeeded), but the configuration is in place and would activate on
a genuinely failing update; a manual rollback is also always available via `docker service
rollback pizza-store_backend`.

## Disaster recovery

A single Swarm manager node is a single point of failure for the cluster's own control plane
(not the application data, which is a separate concern covered by Backup/Restore above) — a
production-grade Swarm cluster needs an odd number of manager nodes (3 or 5) for Raft quorum.
Out of scope for this single-node validation; documented here as a real gap a genuine
multi-node deployment would need to close, not silently assumed away.

## Security hardening

Every credential is a Swarm-native secret (never a plain environment variable or a value
baked into the stack file); `edge-net`/`data-net`/`monitoring-net` segmentation is preserved
and was proven (not just declared) via the DNS-resolution failure above. Docker Engine's own
Swarm control-plane traffic (manager↔worker, overlay network encryption) is encrypted by
default — no additional configuration was needed or added.

## Troubleshooting

**`docker stack deploy` rejects `cpus` as a non-string.** If you try to pre-render this file
through `docker compose config` before feeding it to `docker stack deploy` (a reasonable
instinct, since that is exactly how you would get `${VAR}` substituted from a `.env` file),
the rendered output re-serializes `deploy.resources.limits.cpus: "0.5"` as a bare YAML float
(`cpus: 0.5`), which `docker stack deploy` then rejects with `services.<name>.deploy.resources
.limits.cpus: must be a string`. This was a real failure hit during this Task's validation,
not a hypothetical. Fix: don't pre-render — export the `.env` into the shell and run `docker
stack deploy -c infrastructure/swarm/docker-stack.yml` directly (see Environment above);
`docker stack deploy` performs its own `${VAR}` substitution from the shell environment and
parses the original file text, so the lossy round-trip never happens.

**A stateful service's task won't schedule.** Confirm the target node actually carries the
`pizza-store.data=true` label (`docker node inspect <node-id> --format '{{.Spec.Labels}}'`) —
every stateful service's `placement.constraints` requires it, and an unlabeled single-node
Swarm will leave those tasks pending forever with no clearer error than "no suitable node".

## Validation evidence (2026-11-27)

Real local single-node Swarm (`docker swarm init`), one manager node labeled
`pizza-store.data=true`, full stack deployed via `docker stack deploy -c
infrastructure/swarm/docker-stack.yml pizza-store`:

- All 17 services reached their full desired replica count on the **first** deploy attempt —
  `docker stack services pizza-store` showed `1/1` or `2/2` (and `promtail`'s `global` mode
  showing `1/1`, correct for one node) for every service, no restarts/failures.
- Real traffic through the routing mesh: `curl http://localhost/healthz` → `200`; `curl
  http://localhost/api/v1/ping/` via `/api/` → backend reachable through the edge, `200`.
- Prometheus `up` query returned `1` for all 5 scrape targets (itself + 4 exporters/
  built-in-metrics endpoints) across the overlay network.
- **Real rolling update**: `docker service update --env-add SWARM_ROLLOUT_TEST=issue-158
  pizza-store_backend` — `docker service ps` showed each of the 2 tasks replaced one at a time
  (`start-first` order: new task `Running` before the old one transitioned to `Shutdown`),
  the service reported "converged", and `curl http://localhost/healthz` continued returning
  `200` throughout with no observed downtime window.
- **Network isolation proven, not just declared**: from inside a running `nginx` task,
  `wget http://postgres:5432` failed with `bad address 'postgres:5432'` — a DNS-level failure
  confirming `nginx` has no route to `data-net` at all.
- Clean teardown: `docker stack rm pizza-store` removed all 17 services, 9 secrets, 13
  configs, and 3 networks; `docker swarm leave --force` returned the local Docker daemon to
  `swarm=inactive`, the same state it was in before this validation — no state left behind.
