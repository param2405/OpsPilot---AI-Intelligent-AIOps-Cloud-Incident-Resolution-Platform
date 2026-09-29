# Trust policy allowing ECS tasks to assume the roles
data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    effect  = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# 1. ECS Task Execution Role (Used by AWS ECS Agent to bootstrap the container)
resource "aws_iam_role" "ecs_execution_role" {
  name               = "opspilot-ecs-execution-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "opspilot-ecs-execution-role-${var.environment}"
  }
}

# Attach standard AWS managed policy for pulling from ECR and emitting CloudWatch logs
resource "aws_iam_role_policy_attachment" "ecs_execution_standard" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Custom least-privilege policy allowing retrieval of specific secrets and KMS decryption
data "aws_iam_policy_document" "ecs_execution_secrets" {
  statement {
    sid    = "AllowGetSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue"
    ]
    resources = var.secret_arns
  }

  statement {
    sid    = "AllowKmsDecryptSecrets"
    effect = "Allow"
    actions = [
      "kms:Decrypt"
    ]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name   = "opspilot-ecs-secrets-policy-${var.environment}"
  role   = aws_iam_role.ecs_execution_role.id
  policy = data.aws_iam_policy_document.ecs_execution_secrets.json
}

# 2. ECS Task Role (Used by running OpsPilot application code inside container)
resource "aws_iam_role" "ecs_task_role" {
  name               = "opspilot-ecs-task-role-${var.environment}"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json

  tags = {
    Name = "opspilot-ecs-task-role-${var.environment}"
  }
}

# Least-privilege policy granting S3 artifact access, KMS encryption, and CloudWatch metrics
data "aws_iam_policy_document" "ecs_task_permissions" {
  statement {
    sid    = "AllowS3ArtifactAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = [
      var.artifact_bucket_arn,
      "${var.artifact_bucket_arn}/*"
    ]
  }

  statement {
    sid    = "AllowKmsCryptoForArtifacts"
    effect = "Allow"
    actions = [
      "kms:GenerateDataKey",
      "kms:Decrypt"
    ]
    resources = [var.kms_key_arn]
  }

  statement {
    sid    = "AllowCloudWatchCustomMetrics"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData"
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["OpsPilot/AIOps"]
    }
  }
}

resource "aws_iam_role_policy" "ecs_task_permissions" {
  name   = "opspilot-ecs-app-policy-${var.environment}"
  role   = aws_iam_role.ecs_task_role.id
  policy = data.aws_iam_policy_document.ecs_task_permissions.json
}
