resource "random_id" "suffix" {
  byte_length = 4
}

# =============================================================================
# 1. OpsPilot Artifact Storage Bucket (Runbooks, MLflow checkpoints, Postmortems)
# =============================================================================
resource "aws_s3_bucket" "artifacts" {
  bucket        = "opspilot-artifacts-${var.environment}-${random_id.suffix.hex}"
  force_destroy = false # Prevent accidental automatic data destruction

  tags = {
    Name = "opspilot-artifacts-${var.environment}"
  }
}

# Block all public access unconditionally
resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enforce SSE-KMS Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = var.kms_key_arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# Enable Object Versioning for disaster recovery and rollback protection
resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Cost Control: Lifecycle rules for tiered storage and cleanup
resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "archive-and-cleanup"
    status = "Enabled"

    filter {}

    # Transition active objects to Intelligent-Tiering after 30 days
    transition {
      days          = 30
      storage_class = "INTELLIGENT_TIERING"
    }

    # Transition superseded noncurrent versions to Glacier after 90 days
    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    # Expire deleted noncurrent versions after 365 days
    noncurrent_version_expiration {
      noncurrent_days = 365
    }

    # Clean up incomplete multipart uploads after 7 days
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# =============================================================================
# 2. React Frontend SPA Static Website Bucket (CloudFront Origin)
# =============================================================================
resource "aws_s3_bucket" "frontend" {
  bucket        = "opspilot-frontend-${var.environment}-${random_id.suffix.hex}"
  force_destroy = false

  tags = {
    Name = "opspilot-frontend-${var.environment}"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Enabled"
  }
}
