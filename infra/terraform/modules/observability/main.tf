# 1. Amazon SNS Topic for OpsPilot Incident and Infrastructure Alarms
resource "aws_sns_topic" "alerts" {
  name = "opspilot-alerts-${var.environment}"

  tags = {
    Name = "opspilot-alerts-${var.environment}"
  }
}

resource "aws_sns_topic_subscription" "email" {
  count     = length(var.alert_email_endpoints)
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email_endpoints[count.index]
}

# 2. CloudWatch Alarm: High API 5XX Error Rate
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "OpsPilot-API-High5xxErrors-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Triggers when FastAPI backend returns more than 5 5XX errors within 2 minutes."
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
}

# 3. CloudWatch Alarm: Target Group Unhealthy Host Count
resource "aws_cloudwatch_metric_alarm" "unhealthy_hosts" {
  alarm_name          = "OpsPilot-API-UnhealthyHosts-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Triggers when any ECS API container fails health checks."
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
    TargetGroup  = var.target_group_arn_suffix
  }
}

# 4. CloudWatch Alarm: High ECS Service CPU Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_high_cpu" {
  alarm_name          = "OpsPilot-ECS-API-HighCPU-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "Triggers when ECS API tasks exceed 85% CPU utilization for 3 minutes."
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.api_service_name
  }
}

# 5. CloudWatch Alarm: High ECS Service Memory Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_high_memory" {
  alarm_name          = "OpsPilot-ECS-API-HighMemory-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 90
  alarm_description   = "Triggers when ECS API tasks exceed 90% memory utilization."
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.api_service_name
  }
}

# 6. CloudWatch Alarm: High RDS PostgreSQL CPU Utilization
resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "OpsPilot-RDS-HighCPU-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 120
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Triggers when RDS PostgreSQL CPU utilization exceeds 80%."
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id
  }
}

# 7. CloudWatch Alarm: Low RDS Free Storage Space
resource "aws_cloudwatch_metric_alarm" "rds_low_storage" {
  alarm_name          = "OpsPilot-RDS-LowStorage-${var.environment}"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120 # 5 GB in bytes
  alarm_description   = "Triggers when RDS PostgreSQL free storage drops below 5 GB."
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    DBInstanceIdentifier = var.db_instance_id
  }
}

# 8. Unified CloudWatch Monitoring Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "OpsPilot-Operations-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", var.alb_arn_suffix, { stat = "Sum", period = 60, color = "#1f77b4" }],
            [".", "HTTPCode_Target_2XX_Count", ".", ".", { stat = "Sum", period = 60, color = "#2ca02c" }],
            [".", "HTTPCode_Target_5XX_Count", ".", ".", { stat = "Sum", period = 60, color = "#d62728" }]
          ]
          view    = "timeSeries"
          stacked = false
          title   = "API Traffic & Response Status"
          region  = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", var.alb_arn_suffix, { stat = "p95", period = 60, color = "#ff7f0e" }]
          ]
          view    = "timeSeries"
          title   = "p95 API Latency (Seconds)"
          region  = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.api_service_name, { stat = "Average", period = 60, color = "#1f77b4" }],
            [".", "MemoryUtilization", ".", ".", ".", ".", { stat = "Average", period = 60, color = "#2ca02c" }]
          ]
          view    = "timeSeries"
          title   = "ECS API Task CPU & Memory Utilization (%)"
          region  = "us-east-1"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", var.db_instance_id, { stat = "Average", period = 60, color = "#1f77b4" }],
            [".", "DatabaseConnections", ".", ".", { stat = "Average", period = 60, color = "#9467bd" }]
          ]
          view    = "timeSeries"
          title   = "RDS PostgreSQL CPU & Connection Pool"
          region  = "us-east-1"
        }
      }
    ]
  })
}
