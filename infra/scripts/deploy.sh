#!/usr/bin/env bash
# =============================================================================
# OpsPilot AI — Production AWS Deployment Script (Phase 11)
# =============================================================================
# Usage:
#   ./deploy.sh [development|staging|production] [optional_image_tag]
# =============================================================================

set -euo pipefail

ENVIRONMENT="${1:-development}"
IMAGE_TAG="${2:-$(git rev-parse --short HEAD 2>/dev/null || echo "v0.1.0")}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "================================================================="
echo "Starting OpsPilot AI AWS Deployment"
echo "Target Environment : ${ENVIRONMENT}"
echo "Image Tag          : ${IMAGE_TAG}"
echo "AWS Region         : ${AWS_REGION}"
echo "================================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

# 1. Validate Terraform Configurations
echo "[1/5] Initializing and validating Terraform plan..."
cd "${TERRAFORM_DIR}"
terraform init -reconfigure

terraform plan \
  -var-file="environments/${ENVIRONMENT}.tfvars" \
  -var="container_image_api=${ECR_REPO_API:-opspilot/api}:${IMAGE_TAG}" \
  -var="container_image_worker=${ECR_REPO_WORKER:-opspilot/api}:${IMAGE_TAG}" \
  -out="${ENVIRONMENT}.tfplan"

# Apply infrastructure if confirmed
echo "[2/5] Applying Terraform infrastructure changes..."
terraform apply -auto-approve "${ENVIRONMENT}.tfplan"

# Extract outputs
FRONTEND_BUCKET=$(terraform output -raw frontend_bucket_name)
CLOUDFRONT_DIST_ID=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || terraform output -json | grep -o '"cloudfront_distribution_id": "[^"]*' | cut -d'"' -f4)
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)

# 3. Build & Deploy Frontend SPA to S3
echo "[3/5] Building and syncing React frontend SPA..."
cd "${SCRIPT_DIR}/../.."
npm ci
npm run build

echo "Syncing build assets to s3://${FRONTEND_BUCKET}/"
aws s3 sync dist/ "s3://${FRONTEND_BUCKET}/" --delete --region "${AWS_REGION}"

# 4. Invalidate CloudFront Cache for Instant Propagation
echo "[4/5] Invalidating CloudFront edge cache..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "${CLOUDFRONT_DIST_ID}" \
  --paths "/*" \
  --query "Invalidation.Id" \
  --output text)
echo "CloudFront Invalidation created: ${INVALIDATION_ID}"

# 5. Trigger ECS Rolling Deployment & Health Verification
echo "[5/5] Triggering rolling deployment on ECS Fargate..."
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "opspilot-api-${ENVIRONMENT}" \
  --force-new-deployment \
  --region "${AWS_REGION}" > /dev/null

aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "opspilot-worker-${ENVIRONMENT}" \
  --force-new-deployment \
  --region "${AWS_REGION}" > /dev/null

echo "Waiting for ECS service stability (zero-downtime rolling update)..."
aws ecs wait services-stable \
  --cluster "${ECS_CLUSTER}" \
  --services "opspilot-api-${ENVIRONMENT}" "opspilot-worker-${ENVIRONMENT}" \
  --region "${AWS_REGION}"

echo "================================================================="
echo "OpsPilot AI Deployment Successful!"
echo "CloudFront URL: https://$(terraform -chdir="${TERRAFORM_DIR}" output -raw cloudfront_domain_name)"
echo "================================================================="
