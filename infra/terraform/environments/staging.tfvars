# =============================================================================
# OpsPilot AI — Staging Environment Configuration (Pre-Production Mirror)
# =============================================================================

environment                  = "staging"
aws_region                   = "us-east-1"
vpc_cidr                     = "10.20.0.0/16"
availability_zones           = ["us-east-1a", "us-east-1b"]

# Networking
single_nat_gateway           = true

# Compute: Standard Fargate with multi-task testing
use_fargate_spot             = false
ecs_api_cpu                  = 512
ecs_api_memory               = 1024
ecs_api_desired_count        = 2
ecs_api_max_count            = 4
ecs_worker_cpu               = 256
ecs_worker_memory            = 512
ecs_worker_desired_count     = 1

# Database: Graviton2 small instance, Single-AZ with extended snapshot retention
rds_instance_class           = "db.t4g.small"
rds_multi_az                 = false
rds_allocated_storage        = 30
rds_max_allocated_storage    = 100
rds_backup_retention_period  = 14
rds_deletion_protection      = true

# Cache
elasticache_node_type        = "cache.t4g.micro"
elasticache_num_cache_nodes  = 1

# Logging: 30 days retention
cloudwatch_log_retention_days = 30
