variable "aws_region" {
  description = "The AWS region to deploy all OpsPilot resources into."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Target environment: development, staging, or production."
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated OpsPilot VPC."
  type        = string
  default     = "10.10.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones to distribute subnets across."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "single_nat_gateway" {
  description = "Whether to use a single NAT Gateway across all private subnets to save cost (recommended for dev/staging)."
  type        = bool
  default     = true
}

variable "rds_instance_class" {
  description = "RDS PostgreSQL compute instance class (ARM Graviton2 recommended for price/performance)."
  type        = string
  default     = "db.t4g.micro"
}

variable "rds_multi_az" {
  description = "Whether to provision a multi-AZ standby replica for RDS PostgreSQL."
  type        = bool
  default     = false
}

variable "rds_allocated_storage" {
  description = "Allocated storage in GB for RDS PostgreSQL."
  type        = number
  default     = 20
}

variable "rds_max_allocated_storage" {
  description = "Maximum storage in GB for RDS storage autoscaling."
  type        = number
  default     = 100
}

variable "rds_backup_retention_period" {
  description = "Number of days to retain automated daily RDS snapshots."
  type        = number
  default     = 7
}

variable "rds_deletion_protection" {
  description = "Prevent accidental deletion of the database instance."
  type        = bool
  default     = true
}

variable "elasticache_node_type" {
  description = "Compute instance node type for ElastiCache Redis."
  type        = string
  default     = "cache.t4g.micro"
}

variable "elasticache_num_cache_nodes" {
  description = "Number of cache nodes in the ElastiCache Redis cluster."
  type        = number
  default     = 1
}

variable "ecs_api_cpu" {
  description = "vCPU units allocated for the FastAPI backend task (256 = 0.25 vCPU)."
  type        = number
  default     = 256
}

variable "ecs_api_memory" {
  description = "Memory (MB) allocated for the FastAPI backend task."
  type        = number
  default     = 512
}

variable "ecs_api_desired_count" {
  description = "Desired number of running API container task instances."
  type        = number
  default     = 1
}

variable "ecs_api_max_count" {
  description = "Maximum number of running API container task instances during peak autoscaling."
  type        = number
  default     = 4
}

variable "ecs_worker_cpu" {
  description = "vCPU units allocated for the background telemetry worker task."
  type        = number
  default     = 256
}

variable "ecs_worker_memory" {
  description = "Memory (MB) allocated for the background telemetry worker task."
  type        = number
  default     = 512
}

variable "ecs_worker_desired_count" {
  description = "Desired number of background worker container task instances."
  type        = number
  default     = 1
}

variable "use_fargate_spot" {
  description = "Whether to prioritize Fargate Spot for up to 70% compute cost reduction (ideal for dev/staging)."
  type        = bool
  default     = true
}

variable "container_image_api" {
  description = "ECR image URI for the FastAPI application container."
  type        = string
  default     = "public.ecr.aws/opspilot/api:latest"
}

variable "container_image_worker" {
  description = "ECR image URI for the background worker container."
  type        = string
  default     = "public.ecr.aws/opspilot/api:latest"
}

variable "cloudwatch_log_retention_days" {
  description = "Number of days to retain CloudWatch logs before automatic expiration."
  type        = number
  default     = 14
}

variable "domain_name" {
  description = "Optional custom apex or subdomain (e.g. opspilot.example.com). If empty, standard CloudFront/ALB DNS is used."
  type        = string
  default     = ""
}

variable "alert_email_endpoints" {
  description = "List of SRE/Ops email addresses to subscribe to CloudWatch SNS incident alarms."
  type        = list(string)
  default     = []
}
