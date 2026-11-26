# RDS for PostgreSQL -- managed-AWS equivalent of the `postgres` service in
# infrastructure/compose/docker-compose.yml / infrastructure/swarm/docker-stack.yml.

resource "aws_db_subnet_group" "postgres" {
  name_prefix = "${local.name_prefix}-pg-"
  subnet_ids  = aws_subnet.private[*].id

  tags = { Name = "${local.name_prefix}-pg-subnet-group" }
}

resource "aws_db_instance" "postgres" {
  identifier_prefix = "${local.name_prefix}-pg-"

  engine         = "postgres"
  engine_version = var.rds_engine_version
  instance_class = var.rds_instance_class

  allocated_storage = var.rds_allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.rds_database_name
  username = var.rds_master_username

  # AWS generates, stores, and rotates the master password in Secrets Manager --
  # Terraform never sees or stores the real value (current (2026) best practice,
  # replaces the old pattern of a `password` argument backed by a Terraform-managed secret).
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az                = var.environment == "prod"
  backup_retention_period = 7
  skip_final_snapshot     = var.environment != "prod"
  deletion_protection     = var.environment == "prod"

  tags = { Name = "${local.name_prefix}-postgres" }
}
