# Every variable below carries a placeholder/example default so `terraform validate` and
# `terraform fmt -check` succeed with zero real input (Issue #160). None of these defaults
# are real account identifiers, domains, or credentials -- override them via a real
# `*.tfvars` file (gitignored) before ever running `terraform plan` against an actual
# AWS account, which this Task does not do.

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short project slug used to prefix every resource name."
  type        = string
  default     = "pizza-store"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to spread subnets across (two for cost-conscious HA)."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least two availability zones are required for RDS/DocumentDB Multi-AZ and ALB."
  }
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the public subnets (ALB, NAT gateway), one per AZ."
  type        = list(string)
  default     = ["10.20.0.0/24", "10.20.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the private subnets (ECS tasks, data stores), one per AZ."
  type        = list(string)
  default     = ["10.20.10.0/24", "10.20.11.0/24"]
}

variable "domain_name" {
  description = <<-EOT
    Domain name the ACM certificate is requested for. Placeholder only -- DNS validation
    is never completed by this skeleton (no real domain is owned or configured), so the
    certificate resource is structurally valid but would stay PENDING_VALIDATION forever
    if actually applied without a real, owned domain.
  EOT
  type        = string
  default     = "pizza-store.example.com"
}

# --- ECS / ALB -----------------------------------------------------------------------

variable "backend_image" {
  description = "Backend container image URI (ECR repository:tag). Placeholder account ID."
  type        = string
  default     = "123456789012.dkr.ecr.us-east-1.amazonaws.com/pizza-store-backend:latest"
}

variable "frontend_image" {
  description = "Frontend container image URI (ECR repository:tag). Placeholder account ID."
  type        = string
  default     = "123456789012.dkr.ecr.us-east-1.amazonaws.com/pizza-store-frontend:latest"
}

variable "backend_container_port" {
  description = "Port the backend container listens on (matches BACKEND_PORT in .env.example)."
  type        = number
  default     = 8000
}

variable "frontend_container_port" {
  description = "Port the frontend container (Nginx-served static build) listens on."
  type        = number
  default     = 80
}

variable "ecs_task_cpu" {
  description = "Fargate task-level vCPU units (256 = 0.25 vCPU), per service."
  type        = number
  default     = 256
}

variable "ecs_task_memory" {
  description = "Fargate task-level memory in MiB, per service."
  type        = number
  default     = 512
}

variable "ecs_desired_count" {
  description = "Desired running task count per ECS service."
  type        = number
  default     = 2

  validation {
    condition     = var.ecs_desired_count >= 1
    error_message = "ecs_desired_count must be at least 1."
  }
}

# --- RDS (PostgreSQL) ------------------------------------------------------------------

variable "rds_instance_class" {
  description = "RDS instance class. db.t4g.micro is the smallest Graviton burstable class."
  type        = string
  default     = "db.t4g.micro"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GiB."
  type        = number
  default     = 20
}

variable "rds_engine_version" {
  description = <<-EOT
    PostgreSQL major.minor version. Matches the Compose stack's postgres:16-alpine major
    version (see docs/cloud/aws.md for the full version-parity rationale).
  EOT
  type        = string
  default     = "16.15"
}

variable "rds_database_name" {
  description = "Initial database name (matches POSTGRES_DB in .env.example)."
  type        = string
  default     = "pizza_store"
}

variable "rds_master_username" {
  description = "RDS master username (matches POSTGRES_USER in .env.example)."
  type        = string
  default     = "pizza_store"
}

# --- DocumentDB (MongoDB-compatible) ----------------------------------------------------

variable "documentdb_instance_class" {
  description = "DocumentDB instance class. db.t4g.medium is the smallest Graviton class."
  type        = string
  default     = "db.t4g.medium"
}

variable "documentdb_engine_version" {
  description = <<-EOT
    DocumentDB MongoDB-compatibility track. The Compose stack runs mongo:7 -- DocumentDB
    offers no 7.x-compatible track (only 3.6, 4.0, 5.0, 8.0); 5.0 is used here as the
    better-established LTS-style track. See docs/cloud/aws.md for the compatibility gap
    this project would need to verify before any real migration.
  EOT
  type        = string
  default     = "5.0.0"
}

variable "documentdb_master_username" {
  description = "DocumentDB master username (matches MONGO_INITDB_ROOT_USERNAME)."
  type        = string
  default     = "pizza_store"
}

# --- ElastiCache (Valkey, Redis OSS successor) ------------------------------------------

variable "elasticache_node_type" {
  description = "ElastiCache node type. cache.t4g.micro is the smallest Graviton class."
  type        = string
  default     = "cache.t4g.micro"
}

variable "elasticache_engine" {
  description = <<-EOT
    AWS recommends Valkey over Redis OSS for all new ElastiCache deployments (lower cost,
    all new ElastiCache features land on Valkey first). The Compose stack runs upstream
    redis:7-alpine; Valkey is wire-protocol-compatible with the Redis commands this project
    actually uses. See docs/cloud/aws.md for the parity note.
  EOT
  type        = string
  default     = "valkey"
}

variable "elasticache_engine_version" {
  description = "Valkey engine version."
  type        = string
  default     = "8.1"
}

# --- Amazon MQ (RabbitMQ engine) --------------------------------------------------------

variable "mq_engine_version" {
  description = "Amazon MQ for RabbitMQ engine version."
  type        = string
  default     = "4.3"
}

variable "mq_instance_type" {
  description = <<-EOT
    Amazon MQ broker instance type. mq.m7g (Graviton) is required for RabbitMQ engine
    version 4.x; mq.m5/mq.t3 remain available only for the 3.13 track.
  EOT
  type        = string
  default     = "mq.m7g.large"
}

variable "mq_deployment_mode" {
  description = "SINGLE_INSTANCE for this project's synthetic-dataset scale; CLUSTER_MULTI_AZ for real HA."
  type        = string
  default     = "SINGLE_INSTANCE"

  validation {
    condition     = contains(["SINGLE_INSTANCE", "CLUSTER_MULTI_AZ"], var.mq_deployment_mode)
    error_message = "mq_deployment_mode must be SINGLE_INSTANCE or CLUSTER_MULTI_AZ."
  }
}

variable "mq_admin_username" {
  description = "Amazon MQ admin username (matches RABBITMQ_DEFAULT_USER)."
  type        = string
  default     = "pizza_store"
}
