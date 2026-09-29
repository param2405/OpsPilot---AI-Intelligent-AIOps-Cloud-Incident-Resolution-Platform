data "aws_region" "current" {}

# =============================================================================
# 1. Application Load Balancer (Public Ingress)
# =============================================================================
resource "aws_lb" "api" {
  name               = "opspilot-alb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection = false # Configured via root module if needed

  tags = {
    Name = "opspilot-alb-${var.environment}"
  }
}

resource "aws_lb_target_group" "api" {
  name        = "opspilot-api-tg-${var.environment}"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  # Health Check Configuration against FastAPI liveness probe
  health_check {
    enabled             = true
    path                = "/api/v1/health"
    protocol            = "HTTP"
    port                = "8000"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  deregistration_delay = 30 # Connection draining window

  tags = {
    Name = "opspilot-api-tg-${var.environment}"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# =============================================================================
# 2. CloudWatch Log Groups for Containers
# =============================================================================
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/ecs/opspilot-api-${var.environment}"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = {
    Name = "opspilot-api-logs-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/ecs/opspilot-worker-${var.environment}"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = {
    Name = "opspilot-worker-logs-${var.environment}"
  }
}

# =============================================================================
# 3. Amazon ECS Cluster & Capacity Providers
# =============================================================================
resource "aws_ecs_cluster" "main" {
  name = "opspilot-cluster-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "opspilot-cluster-${var.environment}"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = var.use_fargate_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 100
    base              = 1
  }
}

# =============================================================================
# 4. FastAPI Backend Task Definition & Service
# =============================================================================
resource "aws_ecs_task_definition" "api" {
  family                   = "opspilot-api-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(var.api_cpu)
  memory                   = tostring(var.api_memory)
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "opspilot-api"
      image     = var.container_image_api
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "POSTGRES_HOST", value = var.db_host },
        { name = "POSTGRES_PORT", value = tostring(var.db_port) },
        { name = "POSTGRES_DB", value = var.db_name },
        { name = "POSTGRES_USER", value = var.db_user },
        { name = "REDIS_HOST", value = var.redis_host },
        { name = "REDIS_PORT", value = tostring(var.redis_port) },
        { name = "S3_ARTIFACT_BUCKET", value = var.artifact_bucket_name },
        { name = "AWS_DEFAULT_REGION", value = data.aws_region.current.name }
      ]

      secrets = [
        {
          name      = "POSTGRES_PASSWORD"
          valueFrom = "${var.db_secret_arn}:password::"
        },
        {
          name      = "REDIS_PASSWORD"
          valueFrom = "${var.redis_secret_arn}:auth_token::"
        },
        {
          name      = "JWT_SECRET_KEY"
          valueFrom = "${var.app_secret_arn}:jwt_secret_key::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/api/v1/health || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])

  tags = {
    Name = "opspilot-api-task-${var.environment}"
  }
}

resource "aws_ecs_service" "api" {
  name            = "opspilot-api-${var.environment}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count

  capacity_provider_strategy {
    capacity_provider = var.use_fargate_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 100
    base              = 1
  }

  network_configuration {
    subnets          = var.private_app_subnet_ids
    security_groups  = [var.ecs_tasks_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "opspilot-api"
    container_port   = 8000
  }

  deployment_controller {
    type = "ECS"
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  tags = {
    Name = "opspilot-api-service-${var.environment}"
  }

  depends_on = [aws_lb_listener.http]
}

# =============================================================================
# 5. Background Telemetry Worker Task Definition & Service
# =============================================================================
resource "aws_ecs_task_definition" "worker" {
  family                   = "opspilot-worker-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(var.worker_cpu)
  memory                   = tostring(var.worker_memory)
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "opspilot-worker"
      image     = var.container_image_worker
      essential = true
      command   = ["python", "-m", "app.jobs.worker"]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "LOG_LEVEL", value = "INFO" },
        { name = "POSTGRES_HOST", value = var.db_host },
        { name = "POSTGRES_PORT", value = tostring(var.db_port) },
        { name = "POSTGRES_DB", value = var.db_name },
        { name = "POSTGRES_USER", value = var.db_user },
        { name = "REDIS_HOST", value = var.redis_host },
        { name = "REDIS_PORT", value = tostring(var.redis_port) },
        { name = "S3_ARTIFACT_BUCKET", value = var.artifact_bucket_name },
        { name = "AWS_DEFAULT_REGION", value = data.aws_region.current.name },
        { name = "WORKER_INTERVAL_SECONDS", value = "10" },
        { name = "WORKER_HEARTBEAT_FILE", value = "/tmp/worker_heartbeat" }
      ]

      secrets = [
        {
          name      = "POSTGRES_PASSWORD"
          valueFrom = "${var.db_secret_arn}:password::"
        },
        {
          name      = "REDIS_PASSWORD"
          valueFrom = "${var.redis_secret_arn}:auth_token::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "worker"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "test -f /tmp/worker_heartbeat || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 15
      }
    }
  ])

  tags = {
    Name = "opspilot-worker-task-${var.environment}"
  }
}

resource "aws_ecs_service" "worker" {
  name            = "opspilot-worker-${var.environment}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count

  capacity_provider_strategy {
    capacity_provider = var.use_fargate_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 100
    base              = 1
  }

  network_configuration {
    subnets          = var.private_app_subnet_ids
    security_groups  = [var.ecs_tasks_security_group_id]
    assign_public_ip = false
  }

  tags = {
    Name = "opspilot-worker-service-${var.environment}"
  }
}

# =============================================================================
# 6. Auto Scaling for API Service
# =============================================================================
resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_count
  min_capacity       = var.api_desired_count
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "opspilot-api-cpu-target-tracking-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
