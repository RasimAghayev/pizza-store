# Secrets Manager is the managed-AWS replacement for every file-based Compose secret in
# infrastructure/compose/secrets/*.txt. RDS and DocumentDB manage their own master-user
# secret natively (manage_master_user_password = true in rds.tf/documentdb.tf) -- Terraform
# never sees those passwords. Everything else that needs a generated credential (Amazon MQ
# has no equivalent native-password-management flag; ElastiCache auth tokens; the backend's
# Django secret key and JWT signing key) is generated here with `random`/`tls` and stored
# as a Secrets Manager secret, never as a literal value in this file or in state as plain
# config -- Terraform state itself still contains these values, which is why no backend is
# configured in this skeleton and state is never committed (see versions.tf, .gitignore).

resource "random_password" "mq_admin" {
  length  = 32
  special = false # Amazon MQ broker-user passwords reject several special characters
}

resource "aws_secretsmanager_secret" "mq_admin_password" {
  name_prefix = "${local.name_prefix}/mq-admin-password-"
  tags        = { Name = "${local.name_prefix}-mq-admin-password" }
}

resource "aws_secretsmanager_secret_version" "mq_admin_password" {
  secret_id     = aws_secretsmanager_secret.mq_admin_password.id
  secret_string = random_password.mq_admin.result
}

resource "random_password" "elasticache_auth_token" {
  length  = 64
  special = false # ElastiCache auth tokens reject several special characters
}

resource "aws_secretsmanager_secret" "elasticache_auth_token" {
  name_prefix = "${local.name_prefix}/elasticache-auth-token-"
  tags        = { Name = "${local.name_prefix}-elasticache-auth-token" }
}

resource "aws_secretsmanager_secret_version" "elasticache_auth_token" {
  secret_id     = aws_secretsmanager_secret.elasticache_auth_token.id
  secret_string = random_password.elasticache_auth_token.result
}

# Matches DJANGO_SECRET_KEY (infrastructure/compose/secrets/django_secret_key.txt).
resource "random_password" "django_secret_key" {
  length  = 50
  special = true
}

resource "aws_secretsmanager_secret" "django_secret_key" {
  name_prefix = "${local.name_prefix}/django-secret-key-"
  tags        = { Name = "${local.name_prefix}-django-secret-key" }
}

resource "aws_secretsmanager_secret_version" "django_secret_key" {
  secret_id     = aws_secretsmanager_secret.django_secret_key.id
  secret_string = random_password.django_secret_key.result
}

# Matches the JWT_PRIVATE_KEY RSA keypair (infrastructure/compose/secrets/jwt_private_key.txt).
resource "tls_private_key" "jwt_signing_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "aws_secretsmanager_secret" "jwt_private_key" {
  name_prefix = "${local.name_prefix}/jwt-private-key-"
  tags        = { Name = "${local.name_prefix}-jwt-private-key" }
}

resource "aws_secretsmanager_secret_version" "jwt_private_key" {
  secret_id     = aws_secretsmanager_secret.jwt_private_key.id
  secret_string = tls_private_key.jwt_signing_key.private_key_pem
}
