output "db_password" {
  value     = random_password.db_password.result
  sensitive = true
}

output "redis_auth_token" {
  value     = random_password.redis_auth_token.result
  sensitive = true
}

output "jwt_secret" {
  value     = random_password.jwt_secret.result
  sensitive = true
}

output "database_secret_arn" {
  value = aws_secretsmanager_secret.database.arn
}

output "redis_secret_arn" {
  value = aws_secretsmanager_secret.redis.arn
}

output "application_secret_arn" {
  value = aws_secretsmanager_secret.application.arn
}

output "all_secret_arns" {
  value = [
    aws_secretsmanager_secret.database.arn,
    aws_secretsmanager_secret.redis.arn,
    aws_secretsmanager_secret.application.arn
  ]
}
