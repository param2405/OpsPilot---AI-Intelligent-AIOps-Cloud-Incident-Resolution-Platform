output "sns_alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "dashboard_name" {
  value = aws_cloudwatch_dashboard.main.dashboard_name
}
