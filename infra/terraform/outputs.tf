output "cloudfront_domain_name" {
  description = "The public CloudFront CDN URL for OpsPilot AI (Frontend and API)."
  value       = module.frontend.cloudfront_domain_name
}

output "alb_dns_name" {
  description = "The DNS name of the Application Load Balancer."
  value       = module.compute.alb_dns_name
}

output "ecs_cluster_name" {
  description = "The name of the Amazon ECS cluster."
  value       = module.compute.ecs_cluster_name
}

output "rds_endpoint" {
  description = "The database endpoint address (accessible only within private subnets)."
  value       = module.database.db_instance_endpoint
}

output "redis_endpoint" {
  description = "The Redis cache endpoint address (accessible only within private subnets)."
  value       = module.cache.redis_primary_endpoint
}

output "artifact_bucket_name" {
  description = "The S3 bucket name used for storing runbooks, MLflow artifacts, and postmortems."
  value       = module.storage.artifact_bucket_name
}

output "frontend_bucket_name" {
  description = "The S3 bucket name hosting the React Single Page Application static assets."
  value       = module.storage.frontend_bucket_name
}

output "cloudwatch_dashboard_name" {
  description = "The name of the Amazon CloudWatch operational dashboard."
  value       = module.observability.dashboard_name
}
