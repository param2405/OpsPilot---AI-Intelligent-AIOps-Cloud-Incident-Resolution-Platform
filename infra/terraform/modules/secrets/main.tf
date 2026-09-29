# 1. Random Passwords Generated Securely
resource "random_password" "db_password" {
  length  = 32
  special = false # Avoid special characters that break DB URI escaping
}

resource "random_password" "redis_auth_token" {
  length  = 48
  special = false
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

# 2. Database Secret in AWS Secrets Manager
resource "aws_secretsmanager_secret" "database" {
  name                    = "/${var.environment}/opspilot/database"
  kms_key_id              = var.kms_key_id
  recovery_window_in_days = 7

  tags = {
    Name = "opspilot-db-secret-${var.environment}"
  }
}

resource "aws_secretsmanager_secret_version" "database" {
  secret_id = aws_secretsmanager_secret.database.id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = "" # Injected or populated post-provisioning
    port     = 5432
    username = var.db_username
    password = random_password.db_password.result
    database = var.db_name
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# 3. Redis Secret in AWS Secrets Manager
resource "aws_secretsmanager_secret" "redis" {
  name                    = "/${var.environment}/opspilot/redis"
  kms_key_id              = var.kms_key_id
  recovery_window_in_days = 7

  tags = {
    Name = "opspilot-redis-secret-${var.environment}"
  }
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id
  secret_string = jsonencode({
    host       = ""
    port       = 6379
    auth_token = random_password.redis_auth_token.result
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

# 4. Application Secrets (JWT, LLM API Keys, Webhooks)
resource "aws_secretsmanager_secret" "application" {
  name                    = "/${var.environment}/opspilot/application"
  kms_key_id              = var.kms_key_id
  recovery_window_in_days = 7

  tags = {
    Name = "opspilot-app-secret-${var.environment}"
  }
}

resource "aws_secretsmanager_secret_version" "application" {
  secret_id = aws_secretsmanager_secret.application.id
  secret_string = jsonencode({
    jwt_secret_key = random_password.jwt_secret.result
    log_level      = "INFO"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
