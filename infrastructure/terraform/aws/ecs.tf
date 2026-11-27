# ECS Fargate -- managed-AWS equivalent of the `backend`/`frontend` services. Fargate tasks
# are the serverless-container replacement for both the Compose `build:` sections (ECS never
# builds images, same constraint Swarm has -- infrastructure/swarm/docker-stack.yml's header
# comment) and for the 2-replica rolling-update pattern validated there (Issue #158):
# `aws_ecs_service` performs the equivalent rolling deployment natively via its own
# deployment configuration, no `update_config` translation needed.

resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = { Name = "${local.name_prefix}-cluster" }
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${local.name_prefix}/backend"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${local.name_prefix}/frontend"
  retention_in_days = 14
}

resource "aws_iam_role" "ecs_task_execution" {
  name_prefix = "${local.name_prefix}-ecs-exec-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Least-privilege addition to the managed policy above: the execution role needs to read
# the specific Secrets Manager secrets referenced by the backend task definition's
# `secrets` block below (the managed policy alone does not grant Secrets Manager access).
resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name_prefix = "secrets-access-"
  role        = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_db_instance.postgres.master_user_secret[0].secret_arn,
        aws_docdb_cluster.main.master_user_secret[0].secret_arn,
        aws_secretsmanager_secret.elasticache_auth_token.arn,
        aws_secretsmanager_secret.mq_admin_password.arn,
        aws_secretsmanager_secret.django_secret_key.arn,
        aws_secretsmanager_secret.jwt_private_key.arn,
      ]
    }]
  })
}

# Application-level permissions (e.g. S3 access for media uploads) would attach here as
# this project grows -- intentionally empty beyond the trust policy for this skeleton.
resource "aws_iam_role" "ecs_task" {
  name_prefix = "${local.name_prefix}-ecs-task-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "${local.name_prefix}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "backend"
    image = var.backend_image

    portMappings = [{
      containerPort = var.backend_container_port
      protocol      = "tcp"
    }]

    environment = [
      { name = "POSTGRES_HOST", value = aws_db_instance.postgres.address },
      { name = "POSTGRES_PORT", value = tostring(aws_db_instance.postgres.port) },
      { name = "POSTGRES_DB", value = var.rds_database_name },
      { name = "POSTGRES_USER", value = var.rds_master_username },
      { name = "MONGO_HOST", value = aws_docdb_cluster.main.endpoint },
      { name = "MONGO_PORT", value = tostring(aws_docdb_cluster.main.port) },
      { name = "REDIS_HOST", value = aws_elasticache_replication_group.main.primary_endpoint_address },
      { name = "REDIS_PORT", value = "6379" },
      { name = "RABBITMQ_HOST", value = aws_mq_broker.rabbitmq.instances[0].endpoints[0] },
    ]

    secrets = [
      { name = "POSTGRES_PASSWORD", valueFrom = aws_db_instance.postgres.master_user_secret[0].secret_arn },
      { name = "MONGO_PASSWORD", valueFrom = aws_docdb_cluster.main.master_user_secret[0].secret_arn },
      { name = "REDIS_PASSWORD", valueFrom = aws_secretsmanager_secret.elasticache_auth_token.arn },
      { name = "RABBITMQ_PASSWORD", valueFrom = aws_secretsmanager_secret.mq_admin_password.arn },
      { name = "DJANGO_SECRET_KEY", valueFrom = aws_secretsmanager_secret.django_secret_key.arn },
      { name = "JWT_PRIVATE_KEY", valueFrom = aws_secretsmanager_secret.jwt_private_key.arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.backend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "backend"
      }
    }
  }])

  tags = { Name = "${local.name_prefix}-backend-task" }
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${local.name_prefix}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name  = "frontend"
    image = var.frontend_image

    portMappings = [{
      containerPort = var.frontend_container_port
      protocol      = "tcp"
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "frontend"
      }
    }
  }])

  tags = { Name = "${local.name_prefix}-frontend-task" }
}

resource "aws_ecs_service" "backend" {
  name            = "${local.name_prefix}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = var.backend_container_port
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener_rule.api_to_backend]

  tags = { Name = "${local.name_prefix}-backend-service" }
}

resource "aws_ecs_service" "frontend" {
  name            = "${local.name_prefix}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = var.frontend_container_port
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener.https]

  tags = { Name = "${local.name_prefix}-frontend-service" }
}
