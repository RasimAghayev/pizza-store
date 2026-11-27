# Amazon DocumentDB (MongoDB-compatible) -- managed-AWS equivalent of the `mongodb`
# service. Real caveat, not claimed parity: DocumentDB is MongoDB *wire-protocol*
# compatible, not the same engine -- it does not run real MongoDB server code, has no
# 7.x-compatible track (the Compose stack runs mongo:7), and does not support every
# aggregation operator/index type MongoDB itself does. Before any real migration, this
# project's actual Mongo usage (see backend/*/documents.py or equivalent) would need to be
# checked against DocumentDB's supported-operations list -- see docs/cloud/aws.md.

resource "aws_docdb_subnet_group" "main" {
  name_prefix = "${local.name_prefix}-docdb-"
  subnet_ids  = aws_subnet.private[*].id

  tags = { Name = "${local.name_prefix}-docdb-subnet-group" }
}

resource "aws_docdb_cluster" "main" {
  cluster_identifier_prefix = "${local.name_prefix}-docdb-"

  engine          = "docdb"
  engine_version  = var.documentdb_engine_version
  master_username = var.documentdb_master_username

  # Same manage_master_user_password pattern as RDS (rds.tf) -- Terraform never sees the
  # real password.
  manage_master_user_password = true

  db_subnet_group_name   = aws_docdb_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.documentdb.id]

  storage_encrypted       = true
  backup_retention_period = 7
  skip_final_snapshot     = var.environment != "prod"
  deletion_protection     = var.environment == "prod"

  tags = { Name = "${local.name_prefix}-docdb" }
}

resource "aws_docdb_cluster_instance" "main" {
  count              = var.environment == "prod" ? 2 : 1
  identifier_prefix  = "${local.name_prefix}-docdb-"
  cluster_identifier = aws_docdb_cluster.main.id
  instance_class     = var.documentdb_instance_class

  tags = { Name = "${local.name_prefix}-docdb-instance-${count.index}" }
}
