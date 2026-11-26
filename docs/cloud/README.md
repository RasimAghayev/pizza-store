# Cloud

Cost, security, backup, and scaling comparison for AWS/GCP/Azure (documentation-level only, no resources are created).

See [ADR 0007](../adr/0007-deployment-target-priority.md) for why AWS is the primary provider
(the detailed Terraform skeleton and full comparison) while GCP and Azure receive a lighter
service-mapping comparison.

- [`aws.md`](aws.md) — full architecture, cost/security/backup/scaling comparison, and a
  validated-only Terraform skeleton (`infrastructure/terraform/aws/`). Issue #160.
- [`gcp.md`](gcp.md) — service mapping and a lighter comparison; no Terraform skeleton
  (no managed RabbitMQ-compatible broker). Issue #160.
- [`azure.md`](azure.md) — service mapping and a lighter comparison; no Terraform skeleton
  (same reason as GCP). Issue #160.
- [`comparison.md`](comparison.md) — the cross-cutting table spanning all six deployment
  options (VPS, Swarm, Kubernetes, AWS, GCP, Azure). Issue #160.

> Status: Phase 8 — AWS/GCP/Azure documentation and the AWS Terraform skeleton done
> (Issue #160). No real cloud resource was created for any of it.
