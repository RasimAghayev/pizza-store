# Security-group graph mirrors the edge-net/data-net/monitoring-net isolation proven in
# infrastructure/swarm/docker-stack.yml (Issue #158): only the ALB is open to the internet;
# ECS tasks only accept traffic from the ALB; each data store only accepts traffic from the
# ECS security group, never from the internet or from each other directly.

resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  description = "Internet-facing ALB -- the managed-AWS equivalent of edge-net's Nginx."
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from the internet (redirected to HTTPS by the listener)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from the internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-alb-sg" }
}

resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${local.name_prefix}-ecs-tasks-"
  description = "Backend/frontend Fargate tasks -- the managed-AWS equivalent of data-net's backend member."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Backend/frontend container ports, from the ALB only"
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-ecs-tasks-sg" }
}

resource "aws_security_group" "rds" {
  name_prefix = "${local.name_prefix}-rds-"
  description = "RDS PostgreSQL -- accepts traffic from ECS tasks only, never the internet."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from ECS tasks only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  tags = { Name = "${local.name_prefix}-rds-sg" }
}

resource "aws_security_group" "documentdb" {
  name_prefix = "${local.name_prefix}-docdb-"
  description = "DocumentDB -- accepts traffic from ECS tasks only, never the internet."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "MongoDB wire protocol from ECS tasks only"
    from_port       = 27017
    to_port         = 27017
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  tags = { Name = "${local.name_prefix}-docdb-sg" }
}

resource "aws_security_group" "elasticache" {
  name_prefix = "${local.name_prefix}-cache-"
  description = "ElastiCache (Valkey) -- accepts traffic from ECS tasks only, never the internet."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis-protocol port from ECS tasks only"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  tags = { Name = "${local.name_prefix}-cache-sg" }
}

resource "aws_security_group" "mq" {
  name_prefix = "${local.name_prefix}-mq-"
  description = "Amazon MQ (RabbitMQ engine) -- accepts traffic from ECS tasks only, never the internet."
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "AMQP from ECS tasks only"
    from_port       = 5671
    to_port         = 5671
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  ingress {
    description     = "RabbitMQ management console from ECS tasks only"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  tags = { Name = "${local.name_prefix}-mq-sg" }
}
