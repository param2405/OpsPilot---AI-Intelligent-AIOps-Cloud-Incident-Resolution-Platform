"""Pydantic schemas for Phase 9: Human-In-The-Loop Remediation, Action Allowlists, and Audit Logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class RemediationActionType(str, Enum):
    """Explicit allowlist of permitted remediation actions.
    
    The AI agent is NEVER permitted to execute arbitrary shell, AWS CLI, or SQL commands.
    Only strictly validated allowlisted actions are permitted.
    """
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    CLEAR_CACHE = "clear_cache"
    TOGGLE_CIRCUIT_BREAKER = "toggle_circuit_breaker"


class RemediationStatus(str, Enum):
    """Lifecycle state machine for human-in-the-loop remediation."""
    RECOMMENDED = "RECOMMENDED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class UserRole(str, Enum):
    """Authorization roles for remediation approval boundary."""
    VIEWER = "VIEWER"
    OPERATOR = "OPERATOR"
    SRE_LEAD = "SRE_LEAD"
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    AI_AGENT = "AI_AGENT"  # Explicitly blocked from approving its own actions!


# ---------------------------------------------------------------------------
# Strict Action Parameter Schemas for Allowlist Validation
# ---------------------------------------------------------------------------

class RestartServiceParams(BaseModel):
    service_name: Optional[str] = None
    grace_period_seconds: int = Field(default=30, ge=0, le=120)
    rolling: bool = Field(default=True)


class ScaleServiceParams(BaseModel):
    service_name: Optional[str] = None
    replicas: int = Field(..., ge=1, le=20, description="Target replica count strictly bounded between 1 and 20")
    direction: Optional[str] = Field(default="up")
    reason: Optional[str] = None


class RollbackDeploymentParams(BaseModel):
    service_name: Optional[str] = None
    target_version: Optional[str] = None
    target_revision: Optional[Union[str, int]] = Field(default=None, description="Specific revision or previous healthy release")
    verify_canary: bool = Field(default=True)


class ClearCacheParams(BaseModel):
    service_name: Optional[str] = None
    cache_cluster: str = Field(default="redis-cluster", max_length=64)
    key_pattern: Optional[str] = Field(default=None, max_length=128, description="Key pattern prefix (e.g. session:* or auth:*)")
    cache_prefix: Optional[str] = Field(default=None, max_length=128)


class ToggleCircuitBreakerParams(BaseModel):
    service_name: Optional[str] = None
    dependency_service: Optional[str] = Field(default=None, max_length=64)
    target_state: Optional[str] = Field(default="OPEN", pattern="^(OPEN|CLOSED|HALF_OPEN)$")
    enabled: Optional[bool] = Field(default=True)
    failure_threshold: Optional[int] = Field(default=5, ge=1, le=20)
    reset_timeout_seconds: Optional[int] = Field(default=60, ge=5, le=300)


# ---------------------------------------------------------------------------
# Requests and Responses
# ---------------------------------------------------------------------------

class ApprovalRequest(BaseModel):
    """Request payload for human approval of a remediation action."""
    approved_by: Optional[str] = Field(default=None, max_length=128, description="User identifier (e.g. email or username)")
    user_role: Optional[UserRole] = Field(default=None, description="Caller RBAC role")
    comment: Optional[str] = Field(default=None, max_length=512)


class RejectRequest(BaseModel):
    """Request payload for human rejection of a recommendation."""
    rejected_by: str = Field(..., min_length=3, max_length=128)
    user_role: UserRole = Field(default=UserRole.SRE_LEAD)
    rejection_reason: str = Field(..., min_length=5, max_length=512, description="Mandatory rationale for audit trail")


class SimulateRemediationRequest(BaseModel):
    """Direct invocation of an allowlisted action under human authorization."""
    action_type: RemediationActionType
    target_service: str = Field(..., min_length=2, max_length=64)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    incident_id: Optional[str] = None
    authorized_by: str = Field(..., min_length=3, max_length=128)
    user_role: UserRole = Field(default=UserRole.SRE_LEAD)


class RemediationRecommendationResponse(BaseModel):
    """DTO for viewing remediation recommendations."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    incident_id: str
    investigation_id: Optional[str] = None
    action_type: str
    target_service: str
    parameters: Dict[str, Any]
    rationale: str
    risk_level: str
    status: str
    command_preview: Optional[str] = None
    runbook_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RemediationAuditLogResponse(BaseModel):
    """DTO for viewing remediation audit logs."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    recommendation_id: str
    incident_id: str
    requested_action: str
    action_parameters: Dict[str, Any]
    simulation_mode: bool
    user_approval: Dict[str, Any]
    executor_result: Dict[str, Any]
    status: str
    timestamp: datetime


class ExecutionResultSummary(BaseModel):
    """Detailed summary of the allowlisted action execution."""
    output: str
    execution_duration_ms: float
    simulated: bool
    validation_passed: bool
    logs: List[str]
    rollback_point: Optional[str] = None
