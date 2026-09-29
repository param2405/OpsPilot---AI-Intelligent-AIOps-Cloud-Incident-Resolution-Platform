variable "environment" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "secret_arns" {
  type        = list(string)
  description = "List of Secrets Manager ARNs the execution role is permitted to read."
}

variable "artifact_bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket used for RAG runbooks, MLflow artifacts, and postmortems."
}
