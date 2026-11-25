# ADR 0007: Deployment Target Priority

## Status

Accepted

## Context

Master prompt §8 already fixes the realistic bar across deployment targets: the VPS
(Compose + Nginx + SSL) target must be fully working and tested; Docker Swarm and Kubernetes
manifests must be validated (a lower bar — not necessarily deployed to a real multi-node
production cluster); AWS/GCP/Azure get documentation plus a cost/security/backup/scaling
comparison and a Terraform skeleton, with no real cloud resource created and no paid resource
ever started. §8 does not, however, pick a concrete VPS sizing, a build order between Swarm
and Kubernetes, or which one cloud provider's Terraform skeleton gets the detailed treatment
versus the other two getting a lighter equivalent.

Without this decision, Phase 8 (which implements against §8's bar) could spend uneven effort
— e.g. building Kubernetes manifests before Swarm's simpler stack-file translation has
surfaced the same health-check/secret/config issues that reappear in Kubernetes anyway, or
splitting Terraform effort evenly across three providers instead of going deep on one.

No deployment configuration exists yet beyond the planned `infrastructure/` subfolder
skeletons (`swarm/`, `kubernetes/`, `terraform/`, `ansible/`). This ADR is written purely from
§8 and the stack already fixed by ADR 0001/0002 (PostgreSQL, MongoDB, Redis, RabbitMQ).

## Decision

### Swarm before Kubernetes

Phase 8 builds and validates **Docker Swarm first, Kubernetes second**.

The project already has a Docker Compose stack from Phase 2; a Swarm stack file is a close
syntactic derivative of that Compose file (`docker stack deploy` consumes a Compose-v3-shaped
file with Swarm-specific additions for `deploy:`, `secrets:`, `configs:`), so Swarm validation
mostly exercises the orchestration concerns (overlay networking, secrets, rolling update) on
top of a stack definition the team already understands, rather than also having to learn an
entirely new manifest format at the same time. Kubernetes' manifest set (Deployment, Service,
Ingress, ConfigMap, Secret, StatefulSet, PV, probes, HPA, NetworkPolicy, Helm) is a larger,
unrelated format with no direct Compose-file derivation; building it second means any
health-check, secret-shape, or config-separation issue Swarm's translation surfaces gets fixed
once and carried into the Kubernetes manifests, instead of being discovered independently in
both.

### AWS as the primary cloud provider

**AWS** gets the detailed Terraform skeleton and the full cost/security/backup/scaling
comparison; GCP and Azure each get a lighter equivalent document (service-mapping table plus a
shorter comparison, no full Terraform skeleton of their own).

The deciding factor is messaging-service fit: **Amazon MQ explicitly supports RabbitMQ as a
managed broker engine**, giving AWS the only native managed-service match for this project's
actual messaging choice (ADR 0001). GCP (Pub/Sub) and Azure (Service Bus) have no RabbitMQ-
compatible managed offering — on either, RabbitMQ would have to run self-hosted on compute
instances instead of as a managed service, which is a materially different operational story
worth documenting but not worth building out a full Terraform skeleton for two providers in
parallel. AWS also has a direct managed equivalent for every other piece of the stack (RDS for
PostgreSQL, a MongoDB-compatible managed offering, ElastiCache for Redis), so one coherent
"fully managed" skeleton is possible there without a mixed managed/self-hosted story.

### Generic VPS baseline

A single Ubuntu LTS VPS (current LTS at Phase 8's implementation time), sized at **4 vCPU / 8
GB RAM / 100 GB SSD** — enough headroom to run the full Compose stack (PostgreSQL, MongoDB,
Redis, RabbitMQ, backend, frontend, Nginx) on one host at the synthetic dataset's documented
scale (10 branches, 20,000+ customers, 100,000+ historical orders — master prompt §10), without
sizing for real production traffic this project will never actually serve. Nginx terminates TLS
via Let's Encrypt/certbot, matching the existing `infrastructure/nginx/` skeleton; this is the
"VPS Compose" target that §8 requires to be fully working and tested, not just documented.

### Ansible: deferred

Ansible provisioning is **deferred, "as needed"**, per the existing
`infrastructure/ansible/README.md` skeleton — not committed to as a Phase 8 deliverable.
Ansible's value is consistent, repeatable provisioning across *multiple* hosts; Phase 8's VPS
target is a single documented host, where a plain setup script is sufficient and Ansible would
be infrastructure built ahead of a need that doesn't exist yet. It is picked back up once either
a second VPS-class environment needs provisioning consistency, or Swarm's multi-node setup is
actually instantiated on real infrastructure (beyond manifest validation) and needs repeatable
node provisioning.

## Reason

- Building Swarm first lets the same translation issues (health checks, secret shape,
  config separation) get solved once from the Compose stack's starting point, rather than
  solving them twice independently for Swarm and Kubernetes.
- AWS's Amazon MQ (RabbitMQ engine) is a concrete, checkable differentiator rather than a
  popularity-based choice — it is the only one of the three providers where "fully managed"
  is actually true for this project's exact stack, including the messaging layer.
- Fixing a concrete VPS size now (rather than leaving it unstated) means Phase 8's VPS
  deliverable has a sizing to validate against instead of being written to no particular
  target.
- Deferring Ansible keeps Phase 8 scoped to what §8 actually requires (a working VPS, validated
  Swarm/K8s manifests, documented cloud) instead of adding a provisioning tool with no current
  multi-host need to serve.

## Consequences

- Phase 8's Task breakdown orders Swarm-stack work before Kubernetes-manifest work.
- The AWS Terraform skeleton and its cost/security/backup/scaling comparison get the detailed
  treatment; the GCP and Azure documents are explicitly scoped as lighter service-mapping
  comparisons, not abandoned or silently skipped.
- The VPS deployment doc (per master prompt §8's required per-document sections: Prerequisites,
  Environment, Secrets, Networking, Database setup, Backup/Restore, SSL, Reverse proxy,
  Monitoring, Logging, Scaling, Rollback, Disaster recovery, Security hardening,
  Troubleshooting) is written against the 4 vCPU/8 GB/100 GB baseline fixed here.
- If a genuine multi-host provisioning need appears before Phase 8 closes, Ansible scope is
  revisited via a follow-up decision rather than silently expanding this ADR's deferral.

## Alternatives

- **Kubernetes before Swarm**: rejected — Kubernetes' manifest set has no direct derivation
  from the existing Compose stack, so building it first would mean learning the full manifest
  surface and solving translation issues with no simpler intermediate step, when Swarm already
  provides that step for free given the existing Compose file.
- **GCP or Azure as the primary cloud provider**: rejected — neither offers a managed,
  RabbitMQ-compatible broker; choosing either as primary would mean the "fully managed"
  Terraform skeleton still has to describe a self-hosted messaging component, undermining the
  point of going deep on one provider's managed-service story.
- **Equal lightweight treatment for all three cloud providers (no primary)**: rejected — §8
  already asks for a cost/security/backup/scaling comparison and a Terraform skeleton; spreading
  that evenly across three providers would produce three shallow documents instead of one
  genuinely useful one, with no clearer answer to "which provider would we actually use."
- **Committing to Ansible for Phase 8 now**: rejected — no multi-host provisioning need exists
  yet at the single-VPS stage; adopting it now would be infrastructure built ahead of a
  requirement, which master prompt §0's general bias against speculative work also discourages.
