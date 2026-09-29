output "redis_primary_endpoint" {
  value = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  value = aws_elasticache_replication_group.redis.port
}

output "redis_replication_group_id" {
  value = aws_elasticache_replication_group.redis.id
}
