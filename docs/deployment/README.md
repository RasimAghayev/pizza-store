# Deployment

Local, VPS, Swarm, and Kubernetes deployment strategy and steps.

See [ADR 0007](../adr/0007-deployment-target-priority.md) for the Swarm-before-Kubernetes
build order, the generic VPS baseline sizing, and the Ansible scope decision.

- [`swarm.md`](swarm.md) — Docker Swarm, validated (Issue #158, Phase 8).
- [`kubernetes.md`](kubernetes.md) — Helm/Kubernetes, validated (Issue #159, Phase 8).
- [`vps.md`](vps.md) — VPS (Compose + Nginx + TLS), validated (Issue #157, Phase 8).

See [`docs/cloud/`](../cloud/README.md) for the AWS/GCP/Azure deployment documents and the
cross-cutting comparison spanning all six deployment options (Issue #160).

> Status: Phase 8 — all six deployment targets done (Issues #157, #158, #159, #160).
