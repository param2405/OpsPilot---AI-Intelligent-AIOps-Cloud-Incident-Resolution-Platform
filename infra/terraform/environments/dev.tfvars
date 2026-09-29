# =============================================================================
# OpsPilot AI — Development Environment Configuration (Cost Optimized)
# =============================================================================

environment                  = "development"
aws_region                   = "us-east-1"
vpc_cidr                     = "10.10.0.0/16"
availability_zones           = ["us-east-1a", "us-east-1b"]

# Cost-Control: Single NAT Gateway shared across subnets (~$32/mo savings vs multi-AZ)
single_nat_gateway           = true

# Compute: Fargate Spot for up to 70% cost reduction
use_fargate_spot             = true
ecs_api_cpu                  = 256
ecs_api_memory               = 512
ecs_api_desired_count        = 1
ecs_api_max_count            = 2
ecs_worker_cpu               = 256
ecs_worker_memory            = 512
ecs_worker_desired_count     = 1

# Database: Cost-effective ARM Graviton2, Single-AZ, 7-day backup
rds_instance_class           = "db.t4g.micro"
rds_multi_az                 = false
rds_allocated_storage        = 20
rds_max_allocated_storage    = 50
rds_backup_retention_period  = 7
rds_deletion_protection      = true

# Cache: Minimal Graviton2 node
elasticache_node_type        = "cache.t4g.micro"
elasticache_num_cache_nodes  = 1

# Logging: 14 days retention to minimize CloudWatch log storage fees
cloudwatch_log_retention_days = 14
