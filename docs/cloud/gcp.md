# GCP Deployment (service mapping)

> Status: Phase 8 (Issue #160). Per [ADR 0007](../adr/0007-deployment-target-priority.md),
> GCP gets a lighter service-mapping document — no Terraform skeleton — because it has no
> managed broker matching this project's RabbitMQ choice (ADR 0001); self-hosted RabbitMQ on
> compute is a materially different operational story, documented below rather than built
> out in parallel with [`docs/cloud/aws.md`](aws.md)'s full AWS skeleton. No GCP resource,
> credential, or account was ever created for this document.

## Service mapping

| Compose/Swarm service | GCP equivalent | Notes |
| --- | --- | --- |
| `nginx` (edge) | Cloud Load Balancing (external HTTPS LB) + Google-managed SSL certificate | Same path-based routing role as the AWS ALB in `aws.md`. |
| `backend` / `frontend` | Cloud Run or GKE Autopilot | Cloud Run is the closer analogue to ECS Fargate (serverless, per-request/always-on containers, no node management); GKE Autopilot is the closer analogue if the Kubernetes manifests from Issue #159 are reused directly. |
| `postgres` | Cloud SQL for PostgreSQL | Direct managed equivalent, comparable maturity to RDS. |
| `mongodb` | **No GCP-native managed MongoDB-compatible service.** Firestore offers a MongoDB-compatibility mode (Firestore Enterprise edition), or MongoDB Atlas is sold as a first-class integrated marketplace product running on GCP infrastructure. | Firestore's MongoDB compatibility is a newer, different-underlying-engine offering (not a wire-compatible fork the way DocumentDB is) — any real migration would need the same per-feature verification called out in `aws.md`'s DocumentDB caveat, arguably with a larger gap since the underlying storage engine differs more. MongoDB Atlas on GCP is the closer analogue to "managed MongoDB," but it is a third-party service billed outside GCP's own pricing, not a GCP-native resource. |
| `redis` | Memorystore (for Redis, or for Valkey) | Memorystore explicitly supports Valkey, Redis Cluster, and Redis — same engine-choice flexibility as AWS's ElastiCache. |
| `rabbitmq` | **No GCP-native managed RabbitMQ.** Pub/Sub is GCP's native messaging product but is not AMQP/RabbitMQ-compatible — it is a different API and delivery model, not a drop-in replacement. Real options are (a) a GCP Marketplace partner offering (e.g. CloudAMQP), or (b) self-hosting RabbitMQ on GKE/Compute Engine, which reintroduces the exact operational burden (patching, HA, backup) a managed broker is meant to remove. | This is the concrete reason GCP did not get the detailed treatment (ADR 0007) — every other piece of the stack has a clean managed equivalent, but messaging does not. |
| `infrastructure/compose/secrets/*.txt` | Secret Manager | Direct equivalent to AWS Secrets Manager; same per-secret pricing model. |

## Cost/security/backup/scaling comparison (brief)

- **Cost**: Cloud SQL and Memorystore pricing is in the same order of magnitude as their RDS/
  ElastiCache equivalents in `aws.md`'s table. The dominant cost difference vs. AWS is the
  messaging line: GCP has no managed-broker cost to compare directly — the real cost is
  either a marketplace partner's subscription fee or the compute (plus ongoing operational
  time) of self-hosting RabbitMQ on GKE/Compute Engine, which `aws.md`'s Amazon MQ line item
  (~$200/month) is explicitly avoiding by being a managed service.
- **Security**: Equivalent shape to AWS — VPC-native network isolation, Secret Manager for
  credentials, IAM for per-service least privilege. No material difference from the AWS
  comparison in `aws.md`.
- **Backup**: Cloud SQL offers automated backups and point-in-time recovery comparable to
  RDS. A self-hosted RabbitMQ on GKE/Compute Engine would need this project's own
  `scripts/backup-*.sh`-style approach for the broker, since there is no managed-service
  backup to rely on for that one component.
- **Scaling**: Cloud Run scales to zero and back up per-request, a materially different
  (and for a low/bursty-traffic workload, potentially cheaper) model than ECS Fargate's
  always-on task count or Kubernetes' HPA-driven pod count — worth noting as a GCP-specific
  advantage even though GCP is not the primary provider here.

See [`docs/cloud/comparison.md`](comparison.md) for the full cross-provider table spanning
all six deployment options.
