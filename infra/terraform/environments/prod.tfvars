# =============================================================================
# OpsPilot AI — Production Environment Configuration (High Availability & SLA)
# =============================================================================

environment                  = "production"
aws_region                   = "us-east-1"
vpc_cidr                     = "10.30.0.0/16"
availability_zones           = ["us-east-1a", "us-east-1b", "us-east-1c"]

# Networking: Highly available multi-AZ NAT Gateways
single_nat_gateway           = false

# Compute: Multi-AZ autoscaled Fargate tasks with dedicated CPU/RAM
use_fargate_spot             = false
ecs_api_cpu                  = 1024
ecs_api_memory               = 2048
ecs_api_desired_count        = 2
ecs_api_max_count            = 8
ecs_worker_cpu               = 512
ecs_worker_memory            = 1024
ecs_worker_desired_count     = 2

# Database: Multi-AZ Synchronous Standby Failover, 30 days retention, 100GB+ autoscaling
rds_instance_class           = "db.t4g.medium"
rds_multi_az                 = true
rds_allocated_storage        = 50
rds_max_allocated_storage    = 250
rds_backup_retention_period  = 30
rds_deletion_protection      = true

# Cache: Multi-node HA Redis cluster
elasticache_node_type        = "cache.t4g.small"
elasticache_num_cache_nodes  = 2

# Logging: 90 days retention for compliance and audit
cloudwatch_log_retention_days = 90
