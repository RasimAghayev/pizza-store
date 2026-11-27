# ElastiCache (Valkey) -- managed-AWS equivalent of the `redis` service. Real caveat:
# the Compose stack runs upstream redis:7-alpine; Valkey is the Linux-Foundation-governed
# fork AWS now recommends for every new ElastiCache deployment (lower cost, every new
# ElastiCache feature lands on Valkey first) and is wire/command-compatible with the Redis
# OSS commands this project actually uses -- see docs/cloud/aws.md for the parity note.

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-cache-subnet-group"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${substr(local.name_prefix, 0, 30)}-cache"
  description          = "Valkey cache for ${var.project_name} (${var.environment})"

  engine         = var.elasticache_engine
  engine_version = var.elasticache_engine_version
  node_type      = var.elasticache_node_type

  num_cache_clusters         = var.environment == "prod" ? 2 : 1
  automatic_failover_enabled = var.environment == "prod"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.elasticache.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.elasticache_auth_token.result

  tags = { Name = "${local.name_prefix}-cache" }
}
