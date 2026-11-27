output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.main.dns_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL connection endpoint (host:port)."
  value       = aws_db_instance.postgres.endpoint
}

output "rds_master_user_secret_arn" {
  description = "Secrets Manager ARN holding the RDS master-user credentials."
  value       = aws_db_instance.postgres.master_user_secret[0].secret_arn
}

output "documentdb_endpoint" {
  description = "DocumentDB cluster connection endpoint."
  value       = aws_docdb_cluster.main.endpoint
}

output "documentdb_master_user_secret_arn" {
  description = "Secrets Manager ARN holding the DocumentDB master-user credentials."
  value       = aws_docdb_cluster.main.master_user_secret[0].secret_arn
}

output "elasticache_primary_endpoint" {
  description = "ElastiCache (Valkey) primary endpoint."
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "mq_endpoint" {
  description = "Amazon MQ (RabbitMQ) broker endpoint."
  value       = aws_mq_broker.rabbitmq.instances[0].endpoints[0]
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}
