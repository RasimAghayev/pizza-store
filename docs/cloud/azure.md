# Azure Deployment (service mapping)

> Status: Phase 8 (Issue #160). Per [ADR 0007](../adr/0007-deployment-target-priority.md),
> Azure gets a lighter service-mapping document — no Terraform skeleton — for the same
> reason as GCP (`docs/cloud/gcp.md`): no managed broker matching this project's RabbitMQ
> choice (ADR 0001). No Azure resource, credential, or account was ever created for this
> document.

## Service mapping

| Compose/Swarm service | Azure equivalent | Notes |
| --- | --- | --- |
| `nginx` (edge) | Azure Application Gateway (or Azure Front Door) + Azure-managed TLS certificate | Same path-based routing role as the AWS ALB in [`docs/cloud/aws.md`](aws.md). |
| `backend` / `frontend` | Azure Container Apps or Azure Kubernetes Service (AKS) | Container Apps is the closer analogue to ECS Fargate/Cloud Run (serverless containers, scale-to-zero option); AKS is the closer analogue if the Kubernetes manifests from Issue #159 are reused directly. |
| `postgres` | Azure Database for PostgreSQL (Flexible Server) | Direct managed equivalent, comparable maturity to RDS/Cloud SQL. |
| `mongodb` | Azure Cosmos DB for MongoDB (API for MongoDB) | **A genuinely closer compatibility match than AWS's DocumentDB for this project specifically** — Cosmos DB's MongoDB API supports versions up through v7.0/v8, i.e. it actually covers the `mongo:7` version this project runs, whereas DocumentDB has no 7.x-compatible track at all (`aws.md`'s caveat). Not full parity either — Cosmos DB still does not support every aggregation-pipeline stage or index type real MongoDB does — but worth stating plainly rather than assuming AWS is uniformly ahead on every dimension; Azure's cloud documentation deliberately isn't understated to make AWS's case look stronger than it is. |
| `redis` | Azure Cache for Redis | Direct managed equivalent; Basic/Standard/Premium/Enterprise tiers, comparable to ElastiCache. |
| `rabbitmq` | **No Azure-native managed RabbitMQ.** Azure Service Bus is Azure's native messaging product but speaks neither AMQP 0-9-1 nor the RabbitMQ management API the way RabbitMQ clients expect — not a drop-in replacement. Real options are (a) a Marketplace partner (e.g. CloudAMQP, which explicitly supports Azure Private Link), or (b) self-hosting via the RabbitMQ Cluster Kubernetes Operator on AKS, reintroducing the same operational burden a managed broker removes. | Identical reasoning to GCP's gap (`docs/cloud/gcp.md`) — this is why Azure also did not get the detailed Terraform treatment despite the closer MongoDB match above. |
| `infrastructure/compose/secrets/*.txt` | Azure Key Vault | Direct equivalent to AWS Secrets Manager/GCP Secret Manager. |

## Cost/security/backup/scaling comparison (brief)

- **Cost**: Azure Database for PostgreSQL and Azure Cache for Redis sit in the same order of
  magnitude as their AWS/GCP equivalents. As with GCP, the real cost difference vs. AWS is
  the messaging line — either a Marketplace partner subscription or the compute/operational
  cost of self-hosting RabbitMQ on AKS, since there is no managed-broker line item to
  compare directly against `aws.md`'s ~$200/month Amazon MQ estimate.
- **Security**: Equivalent shape to AWS/GCP — VNet-native network isolation, Key Vault for
  credentials, Azure RBAC for per-service least privilege. No material difference from the
  AWS comparison in `aws.md`.
- **Backup**: Azure Database for PostgreSQL offers automated backups and point-in-time
  restore comparable to RDS/Cloud SQL. Cosmos DB has its own continuous-backup model
  (distinct from, and in some tiers more granular than, RDS/DocumentDB's snapshot model) —
  worth noting as a genuine Azure strength alongside the MongoDB-compatibility note above.
- **Scaling**: Azure Container Apps' scale-to-zero model is the same category of advantage
  Cloud Run offers on GCP — a materially different cost/scaling story than ECS Fargate's
  always-on task count for a low/bursty-traffic workload, even though Azure is not the
  primary provider here.

See [`docs/cloud/comparison.md`](comparison.md) for the full cross-provider table spanning
all six deployment options.
