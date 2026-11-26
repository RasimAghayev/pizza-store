# Docker Swarm

`docker-stack.yml` — a Docker Swarm translation of `infrastructure/compose/
docker-compose.yml` (Issue #158, ADR 0007 "Swarm before Kubernetes"): three overlay networks,
Swarm-native secrets/configs (sourced from the same files the Compose stack already uses, no
duplicate secret material), `deploy:` blocks (replicas, rolling-update config, resource
limits, placement constraints for stateful services), and `backend`/`frontend`/`nginx`
replicated at 2 to exercise a real rolling update.

See [`docs/deployment/swarm.md`](../../docs/deployment/swarm.md) for the full deployment
procedure, every required §8 documentation section, and real validation evidence (a clean
first-attempt deploy of all 17 services, a real zero-downtime rolling update, and a proven
network-isolation check on a local single-node Swarm).

> Status: Phase 8 (Issue #158) — validated on a real local single-node Swarm. Kubernetes
> (Issue #159) builds on this per ADR 0007's build order.
