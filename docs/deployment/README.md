# Deployment

Local, VPS, Swarm, and Kubernetes deployment strategy and steps.

See [ADR 0007](../adr/0007-deployment-target-priority.md) for the Swarm-before-Kubernetes
build order, the generic VPS baseline sizing, and the Ansible scope decision.

- [`swarm.md`](swarm.md) — Docker Swarm, validated (Issue #158, Phase 8).
- `kubernetes.md` — Helm/Kubernetes, not yet written (Issue #159).
- `vps.md` — VPS (Compose + Nginx + TLS), not yet written (Issue #157).

> Status: Phase 8 — Docker Swarm done (Issue #158); VPS and Kubernetes still in progress.
