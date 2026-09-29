#!/usr/bin/env bash
# =============================================================================
# OpsPilot AI — Production Emergency Rollback Script (Phase 11)
# =============================================================================
# Usage:
#   ./rollback.sh [development|staging|production] [target_task_revision_or_previous]
# =============================================================================

set -euo pipefail

ENVIRONMENT="${1:-development}"
TARGET_REVISION="${2:-previous}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo "================================================================="
echo "INSPECTING EMERGENCY ROLLBACK FOR: ${ENVIRONMENT}"
echo "================================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

cd "${TERRAFORM_DIR}"
ECS_CLUSTER=$(terraform output -raw ecs_cluster_name)
FRONTEND_BUCKET=$(terraform output -raw frontend_bucket_name)

# 1. Determine Previous Task Definition Revision
CURRENT_API_DEF=$(aws ecs describe-services \
  --cluster "${ECS_CLUSTER}" \
  --services "opspilot-api-${ENVIRONMENT}" \
  --query "services[0].taskDefinition" \
  --output text \
  --region "${AWS_REGION}")

CURRENT_REV=$(echo "${CURRENT_API_DEF}" | awk -F':' '{print $NF}')

if [ "${TARGET_REVISION}" = "previous" ]; then
  ROLLBACK_REV=$((CURRENT_REV - 1))
else
  ROLLBACK_REV="${TARGET_REVISION}"
fi

echo "Current Task Revision  : ${CURRENT_REV}"
echo "Rolling Back to Target : ${ROLLBACK_REV}"

if [ "${ROLLBACK_REV}" -lt 1 ]; then
  echo "Error: Cannot roll back below revision 1."
  exit 1
fi

# 2. Revert ECS Services to Target Revision
echo "[1/3] Updating ECS API service to revision ${ROLLBACK_REV}..."
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "opspilot-api-${ENVIRONMENT}" \
  --task-definition "opspilot-api-${ENVIRONMENT}:${ROLLBACK_REV}" \
  --force-new-deployment \
  --region "${AWS_REGION}"

echo "[2/3] Updating ECS Worker service to revision ${ROLLBACK_REV}..."
aws ecs update-service \
  --cluster "${ECS_CLUSTER}" \
  --service "opspilot-worker-${ENVIRONMENT}" \
  --task-definition "opspilot-worker-${ENVIRONMENT}:${ROLLBACK_REV}" \
  --force-new-deployment \
  --region "${AWS_REGION}"

# 3. Wait for Healthy Stability
echo "[3/3] Waiting for rollback tasks to stabilize..."
aws ecs wait services-stable \
  --cluster "${ECS_CLUSTER}" \
  --services "opspilot-api-${ENVIRONMENT}" "opspilot-worker-${ENVIRONMENT}" \
  --region "${AWS_REGION}"

echo "================================================================="
echo "Rollback to revision ${ROLLBACK_REV} completed successfully!"
echo "================================================================="
