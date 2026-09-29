# =============================================================================
# OpsPilot AI — Master Terraform Topology Definition (Phase 11)
# =============================================================================

# 1. Dedicated Multi-Tier Virtual Private Cloud (VPC)
module "networking" {
  source             = "./modules/networking"
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  single_nat_gateway = var.single_nat_gateway
}

# 2. KMS Key & Least-Privilege Security Groups
module "security" {
  source      = "./modules/security"
  environment = var.environment
  vpc_id      = module.networking.vpc_id
}

# 3. Object Storage for Artifacts (Runbooks, MLflow, Logs) and React Frontend SPA
module "storage" {
  source      = "./modules/storage"
  environment = var.environment
  kms_key_arn = module.security.kms_key_arn
}

# 4. AWS Secrets Manager with KMS Customer Managed Key
module "secrets" {
  source      = "./modules/secrets"
  environment = var.environment
  kms_key_id  = module.security.kms_key_id
}

# 5. Least-Privilege IAM Roles for ECS Execution and Application Task
module "iam" {
  source              = "./modules/iam"
  environment         = var.environment
  kms_key_arn         = module.security.kms_key_arn
  secret_arns         = module.secrets.all_secret_arns
  artifact_bucket_arn = module.storage.artifact_bucket_arn
}

# 6. Amazon RDS PostgreSQL with pgvector (Private Isolated Subnets)
module "database" {
  source                  = "./modules/database"
  environment             = var.environment
  database_subnet_ids     = module.networking.private_db_subnet_ids
  rds_security_group_id   = module.security.rds_security_group_id
  kms_key_arn             = module.security.kms_key_arn
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  max_allocated_storage   = var.rds_max_allocated_storage
  multi_az                = var.rds_multi_az
  backup_retention_period = var.rds_backup_retention_period
  deletion_protection     = var.rds_deletion_protection
  db_password             = module.secrets.db_password
}

# 7. Amazon ElastiCache Redis In-Memory Broker & Cache (Private Isolated Subnets)
module "cache" {
  source                  = "./modules/cache"
  environment             = var.environment
  database_subnet_ids     = module.networking.private_db_subnet_ids
  redis_security_group_id = module.security.redis_security_group_id
  kms_key_arn             = module.security.kms_key_arn
  node_type               = var.elasticache_node_type
  num_cache_nodes         = var.elasticache_num_cache_nodes
  redis_auth_token        = module.secrets.redis_auth_token
}

# 8. Serverless ECS Fargate Compute & Application Load Balancer
module "compute" {
  source                        = "./modules/compute"
  environment                   = var.environment
  vpc_id                        = module.networking.vpc_id
  public_subnet_ids             = module.networking.public_subnet_ids
  private_app_subnet_ids        = module.networking.private_app_subnet_ids
  alb_security_group_id         = module.security.alb_security_group_id
  ecs_tasks_security_group_id   = module.security.ecs_tasks_security_group_id
  ecs_execution_role_arn        = module.iam.ecs_execution_role_arn
  ecs_task_role_arn             = module.iam.ecs_task_role_arn
  container_image_api           = var.container_image_api
  container_image_worker        = var.container_image_worker
  api_cpu                       = var.ecs_api_cpu
  api_memory                    = var.ecs_api_memory
  api_desired_count             = var.ecs_api_desired_count
  api_max_count                 = var.ecs_api_max_count
  worker_cpu                    = var.ecs_worker_cpu
  worker_memory                 = var.ecs_worker_memory
  worker_desired_count          = var.ecs_worker_desired_count
  use_fargate_spot              = var.use_fargate_spot
  db_host                       = module.database.db_instance_address
  db_port                       = module.database.db_instance_port
  db_secret_arn                 = module.secrets.database_secret_arn
  redis_host                    = module.cache.redis_primary_endpoint
  redis_port                    = module.cache.redis_port
  redis_secret_arn              = module.secrets.redis_secret_arn
  app_secret_arn                = module.secrets.application_secret_arn
  artifact_bucket_name          = module.storage.artifact_bucket_name
  cloudwatch_log_retention_days = var.cloudwatch_log_retention_days
}

# 9. Amazon CloudFront CDN with S3 Origin Access Control & ALB Dynamic Route
module "frontend" {
  source                      = "./modules/frontend"
  environment                 = var.environment
  frontend_bucket_id          = module.storage.frontend_bucket_name
  frontend_bucket_arn         = module.storage.frontend_bucket_arn
  frontend_bucket_domain_name = module.storage.frontend_bucket_domain_name
  alb_dns_name                = module.compute.alb_dns_name
}

# 10. Observability: CloudWatch Alarms, SNS Alerts & Operations Dashboard
module "observability" {
  source                  = "./modules/observability"
  environment             = var.environment
  ecs_cluster_name        = module.compute.ecs_cluster_name
  api_service_name        = module.compute.api_service_name
  worker_service_name     = module.compute.worker_service_name
  alb_arn_suffix          = module.compute.alb_arn_suffix
  target_group_arn_suffix = module.compute.alb_target_group_arn_suffix
  db_instance_id          = module.database.db_instance_id
  alert_email_endpoints   = var.alert_email_endpoints
}
