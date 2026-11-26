# Terraform

Infrastructure-as-code skeleton without locking into any specific cloud provider.

`aws/` (Issue #160, ADR 0007) is a validated-only AWS skeleton: VPC with public/private
subnets, an ALB fronting two ECS Fargate services (`backend`/`frontend`), RDS for
PostgreSQL, Amazon DocumentDB, ElastiCache (Valkey), Amazon MQ (RabbitMQ engine), and
Secrets Manager for every credential. No backend is configured and no AWS credential
exists anywhere in this repository — `terraform validate`/`fmt -check` are run locally
against the public provider registry only; `terraform plan`/`apply` must never be run
against a real account from this skeleton (master prompt §8/§18).

See [`docs/cloud/aws.md`](../../docs/cloud/aws.md) for the full architecture rationale and
cost/security/backup/scaling comparison, and
[`docs/cloud/comparison.md`](../../docs/cloud/comparison.md) for how this fits alongside
VPS/Swarm/Kubernetes/GCP/Azure.

> Status: Phase 8 (Issue #160) — AWS skeleton validated (`terraform validate`/`fmt -check`
> clean). GCP/Azure get documentation only, no Terraform skeleton (see ADR 0007).
