# DB Subnet Group placing RDS exclusively in Private Isolated Subnets
resource "aws_db_subnet_group" "rds" {
  name        = "opspilot-db-subnet-group-${var.environment}"
  description = "Private isolated database subnets for OpsPilot RDS"
  subnet_ids  = var.database_subnet_ids

  tags = {
    Name = "opspilot-db-subnet-group-${var.environment}"
  }
}

# DB Parameter Group enabling pgvector extension and enforcing SSL
resource "aws_db_parameter_group" "pgvector" {
  name        = "opspilot-pg16-pgvector-${var.environment}"
  family      = "postgres16"
  description = "PostgreSQL 16 parameter group enabling pgvector extension and SSL"

  parameter {
    name  = "shared_preload_libraries"
    value = "pgvector"
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  tags = {
    Name = "opspilot-pg16-pgvector-${var.environment}"
  }
}

# Amazon RDS PostgreSQL Database Instance
resource "aws_db_instance" "postgres" {
  identifier                  = "opspilot-postgres-${var.environment}"
  engine                      = "postgres"
  engine_version              = "16.2"
  instance_class              = var.instance_class
  allocated_storage           = var.allocated_storage
  max_allocated_storage       = var.max_allocated_storage
  storage_type                = "gp3"
  storage_encrypted           = true
  kms_key_id                  = var.kms_key_arn

  db_name                     = var.db_name
  username                    = var.db_username
  password                    = var.db_password
  port                        = 5432

  multi_az                    = var.multi_az
  db_subnet_group_name        = aws_db_subnet_group.rds.name
  vpc_security_group_ids      = [var.rds_security_group_id]
  parameter_group_name        = aws_db_parameter_group.pgvector.name
  publicly_accessible         = false

  backup_retention_period     = var.backup_retention_period
  backup_window               = "03:00-04:00"
  maintenance_window          = "Mon:04:30-Mon:05:30"
  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false

  # Safe Destruction Protection
  deletion_protection         = var.deletion_protection
  skip_final_snapshot         = false
  final_snapshot_identifier   = "opspilot-postgres-${var.environment}-final-snapshot"
  copy_tags_to_snapshot       = true

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "opspilot-postgres-${var.environment}"
  }
}
