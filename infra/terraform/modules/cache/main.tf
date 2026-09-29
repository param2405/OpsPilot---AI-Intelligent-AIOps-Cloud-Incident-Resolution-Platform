# Subnet Group for ElastiCache Redis in Private Isolated Subnets
resource "aws_elasticache_subnet_group" "redis" {
  name        = "opspilot-redis-subnet-group-${var.environment}"
  description = "Private isolated database subnets for OpsPilot Redis"
  subnet_ids  = var.database_subnet_ids

  tags = {
    Name = "opspilot-redis-subnet-group-${var.environment}"
  }
}

# ElastiCache Redis Replication Group
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "opspilot-redis-${var.environment}"
  description                = "OpsPilot in-memory cache, task queue broker, and rate limiter"
  node_type                  = var.node_type
  num_cache_clusters         = var.num_cache_nodes
  port                       = 6379
  parameter_group_name       = "default.redis7"
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [var.redis_security_group_id]

  # Security & Compliance
  at_rest_encryption_enabled = true
  kms_key_id                 = var.kms_key_arn
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  automatic_failover_enabled = var.num_cache_nodes > 1 ? true : false
  auto_minor_version_upgrade = true
  maintenance_window         = "sun:05:00-sun:06:00"

  tags = {
    Name = "opspilot-redis-${var.environment}"
  }
}
