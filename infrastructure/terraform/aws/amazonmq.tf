# Amazon MQ (RabbitMQ engine) -- managed-AWS equivalent of the `rabbitmq` service. This is
# the specific reason AWS was chosen as the primary/detailed cloud provider (ADR 0007):
# Amazon MQ is the only one of the three providers' managed broker offerings with a native
# RabbitMQ engine matching this project's actual messaging choice (ADR 0001) -- GCP/Azure
# have no equivalent, hence the lighter self-hosted-RabbitMQ-on-compute treatment in
# docs/cloud/gcp.md / docs/cloud/azure.md.

resource "aws_mq_broker" "rabbitmq" {
  broker_name = "${local.name_prefix}-rabbitmq"

  engine_type        = "RabbitMQ"
  engine_version     = var.mq_engine_version
  host_instance_type = var.mq_instance_type
  deployment_mode    = var.mq_deployment_mode

  subnet_ids      = var.mq_deployment_mode == "CLUSTER_MULTI_AZ" ? aws_subnet.private[*].id : [aws_subnet.private[0].id]
  security_groups = [aws_security_group.mq.id]

  publicly_accessible = false

  user {
    username = var.mq_admin_username
    password = random_password.mq_admin.result
  }

  encryption_options {
    use_aws_owned_key = true
  }

  logs {
    general = true
  }

  tags = { Name = "${local.name_prefix}-rabbitmq" }
}
