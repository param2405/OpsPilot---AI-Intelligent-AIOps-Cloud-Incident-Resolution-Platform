output "alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "alb_arn" {
  value = aws_lb.api.arn
}

output "alb_arn_suffix" {
  value = aws_lb.api.arn_suffix
}

output "alb_target_group_arn" {
  value = aws_lb_target_group.api.arn
}

output "alb_target_group_arn_suffix" {
  value = aws_lb_target_group.api.arn_suffix
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "ecs_cluster_id" {
  value = aws_ecs_cluster.main.id
}

output "api_service_name" {
  value = aws_ecs_service.api.name
}

output "worker_service_name" {
  value = aws_ecs_service.worker.name
}
