# AWS KMS Customer Managed Key (CMK) with automated rotation
resource "aws_kms_key" "main" {
  description             = "OpsPilot KMS key for encrypting RDS, S3, Secrets Manager, and CloudWatch logs in ${var.environment}"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "opspilot-kms-${var.environment}"
  }
}

resource "aws_kms_alias" "main" {
  name          = "alias/opspilot-${var.environment}"
  target_key_id = aws_kms_key.main.key_id
}

# 1. Security Group: Application Load Balancer
resource "aws_security_group" "alb" {
  name        = "opspilot-alb-sg-${var.environment}"
  description = "Allows inbound HTTPS and HTTP traffic to public ALB"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow inbound HTTP from internet for redirect"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow inbound HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Forward traffic to private ECS tasks"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "opspilot-alb-sg-${var.environment}"
  }
}

# 2. Security Group: ECS Fargate Application Tasks (API & Background Worker)
resource "aws_security_group" "ecs_tasks" {
  name        = "opspilot-ecs-tasks-sg-${var.environment}"
  description = "Allows inbound traffic to FastAPI strictly from ALB, and allows worker egress"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow inbound HTTP strictly from ALB security group"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow outbound traffic for NAT Gateway, S3, and AWS services"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "opspilot-ecs-tasks-sg-${var.environment}"
  }
}

# 3. Security Group: Amazon RDS PostgreSQL
resource "aws_security_group" "rds" {
  name        = "opspilot-rds-sg-${var.environment}"
  description = "Allows inbound PostgreSQL traffic strictly from ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow PostgreSQL port 5432 strictly from ECS tasks security group"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "No outbound traffic permitted"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []
  }

  tags = {
    Name = "opspilot-rds-sg-${var.environment}"
  }
}

# 4. Security Group: Amazon ElastiCache Redis
resource "aws_security_group" "redis" {
  name        = "opspilot-redis-sg-${var.environment}"
  description = "Allows inbound Redis traffic strictly from ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Allow Redis port 6379 strictly from ECS tasks security group"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "No outbound traffic permitted"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = []
  }

  tags = {
    Name = "opspilot-redis-sg-${var.environment}"
  }
}
