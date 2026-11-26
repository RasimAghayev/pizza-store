# Application Load Balancer + ACM certificate -- the managed-AWS replacement for the
# Nginx-as-edge role played by infrastructure/nginx/conf.d/default.conf in the
# Compose/Swarm stacks. "Nginx as the edge" is a Compose/Swarm/Kubernetes-specific shape;
# the managed-AWS equivalent terminates TLS at the ALB with an ACM-issued certificate
# instead of a certbot-managed one on a server Nginx owns (see Issue #157's VPS approach
# for the certbot path, which does not apply here).

resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name_prefix}-cert" }
}

resource "aws_lb" "main" {
  name_prefix        = substr(local.name_prefix, 0, 6)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  tags = { Name = "${local.name_prefix}-alb" }
}

resource "aws_lb_target_group" "backend" {
  name_prefix = "bknd-"
  port        = var.backend_container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip" # required for awsvpc network mode (Fargate)

  health_check {
    path                = "/api/schema/"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name_prefix}-backend-tg" }
}

resource "aws_lb_target_group" "frontend" {
  name_prefix = "fnt-"
  port        = var.frontend_container_port
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
    matcher             = "200"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = { Name = "${local.name_prefix}-frontend-tg" }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate.main.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

# /api/* routes to the backend target group; everything else (default action above)
# routes to the frontend target group -- mirrors infrastructure/nginx/conf.d/default.conf's
# location-block split between the Angular SPA and the Django API.
resource "aws_lb_listener_rule" "api_to_backend" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }
}
