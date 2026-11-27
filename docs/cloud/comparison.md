# Deployment Option Comparison

Cross-cutting comparison across every deployment target master prompt §8 asks for: VPS,
Docker Swarm, Kubernetes, AWS, GCP, Azure. See [ADR 0007](../adr/0007-deployment-target-priority.md)
for why Swarm was built before Kubernetes and why AWS got the detailed cloud treatment while
GCP/Azure got lighter service-mapping documents.

| | VPS | Docker Swarm | Kubernetes | AWS | GCP | Azure |
| --- | --- | --- | --- | --- | --- | --- |
| **Status** | Validated end to end with real TLS (Issue #157, closed) | Validated on a real local single-node cluster (Issue #158, closed) | Validated end to end on a real local `kind` cluster (Issue #159, closed) | Terraform skeleton validated (`terraform validate`/`fmt -check` clean), no real resource created (Issue #160, this document) | Documentation only, no resources (Issue #160) | Documentation only, no resources (Issue #160) |
| **Build target** | Single Ubuntu LTS host, 4 vCPU / 8 GB RAM / 100 GB SSD (ADR 0007) | Overlay networks, Swarm-native secrets/configs, placement constraints for stateful services | Deployment/Service/Ingress/ConfigMap/Secret/StatefulSet/HPA/NetworkPolicy via Helm — builds on Swarm's translation (ADR 0007) | VPC + ALB + ECS Fargate + RDS + DocumentDB + ElastiCache + Amazon MQ + Secrets Manager | Cloud Load Balancing + Cloud Run/GKE + Cloud SQL + Firestore/Atlas + Memorystore + (no managed broker) | App Gateway + Container Apps/AKS + Azure DB for PostgreSQL + Cosmos DB + Azure Cache for Redis + (no managed broker) |
| **Messaging (RabbitMQ)** | Self-hosted, same `rabbitmq` container as Compose | Self-hosted, same image, Swarm-managed | Self-hosted, same image, Kubernetes-managed | **Native managed match** — Amazon MQ (RabbitMQ engine) | No managed match — Marketplace partner or self-hosted on GKE | No managed match — Marketplace partner or self-hosted on AKS |
| **MongoDB compatibility** | Exact — same `mongo:7` image | Exact — same image | Exact — same image | DocumentDB: no 7.x-compatible track (nearest is 5.0 or 8.0) | Firestore MongoDB-compatibility mode or MongoDB Atlas (third-party) | Cosmos DB for MongoDB: supports up to v7.0/v8 API — closer match than AWS for this specific project |
| **Cost model** | Fixed (already-rented/owned host), near-zero marginal cost per workload | Same as VPS — this project's own compute | Same as VPS/Swarm | ~$365–385/month non-prod estimate (`docs/cloud/aws.md`), dominated by Amazon MQ + DocumentDB | Same order of magnitude minus the managed-broker line (self-hosted/Marketplace instead) | Same order of magnitude minus the managed-broker line (self-hosted/Marketplace instead) |
| **Who owns HA/patching/failover** | This project (manual, scripted) | This project, with Swarm's own rolling-update/health-check mechanics assisting | This project, with Kubernetes' own mechanics assisting | AWS (RDS/DocumentDB/ElastiCache/Amazon MQ Multi-AZ options) | GCP (Cloud SQL/Memorystore HA options) for everything except messaging | Azure (Azure DB/Cosmos DB/Azure Cache HA options) for everything except messaging |
| **Backup mechanism** | `scripts/backup-postgres.sh`/`backup-mongodb.sh`, `gpg`-encrypted (`docs/runbooks/backup-restore.md`) | Same scripts, pointed at the Swarm-deployed container | Same scripts, pointed at the Kubernetes-deployed pod | RDS/DocumentDB automated snapshots, `backup_retention_period = 7` | Cloud SQL automated backups | Azure DB automated backups; Cosmos DB continuous backup |
| **Network isolation model** | Docker bridge networks (same as local Compose) | Overlay networks — proven via a real DNS-resolution failure (Issue #158) | Kubernetes `NetworkPolicy` — proven via a real timing-based block/allow test on Calico (Issue #159) | VPC public/private subnets + per-tier security groups | VPC-native equivalent | VNet-native equivalent |
| **Horizontal scaling of stateless services** | Manual (single host — limited by host capacity) | `docker service scale`, routing mesh adapts automatically (proven in Issue #158's rolling-update validation) | HPA (CPU/memory) on `backend`/`frontend` — declared in the chart (Issue #159), not load-tested | Application Auto Scaling on ECS service (not yet wired in the Issue #160 skeleton — `ecs_desired_count` is currently static) | Cloud Run scales to zero and back automatically | Container Apps scales to zero and back automatically |
| **Stateful services scaling** | Not horizontally scaled — single host | Not horizontally scaled — `placement.constraints` pins each to one labeled node (Issue #158) | Not horizontally scaled — StatefulSet + PV, one replica per data store | Not horizontally scaled — vertical (instance class) or read-replica only | Same vertical/read-replica-only model | Same vertical/read-replica-only model |

## How to read this table

- The VPS/Swarm/Kubernetes columns run the exact same application images this project
  already builds (`backend`, `frontend`) and the exact same `postgres:16`/`mongo:7`/
  `redis:7`/`rabbitmq:3-management` images — zero compatibility gap, because nothing is
  actually managed by the cloud provider.
- The AWS/GCP/Azure columns trade that exactness for operational offload — every row in
  "who owns HA/patching/failover" that says a cloud provider instead of "this project" is
  the actual value proposition of going managed, and every compatibility caveat in this row
  and the "MongoDB compatibility" row is the real cost of that trade, documented rather than
  hidden.
- No real cloud resource was created to produce this table (master prompt §8/§18) — the AWS
  figures come from a validated-only Terraform skeleton (`terraform validate`/`fmt -check`)
  plus publicly published pricing pages; the GCP/Azure figures come from public
  documentation only.
