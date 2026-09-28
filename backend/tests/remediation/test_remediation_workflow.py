"""Tests for Phase 9: Human-In-The-Loop Remediation Workflow, Allowlist Validation,
RBAC Authorization Boundaries, and Immutable Audit Logging.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security_remediation import RemediationAuthorizationError, verify_approval_authorization
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.incident import Incident
from app.models.remediation import RemediationAuditLog, RemediationRecommendation
from app.schemas.remediation import (
    ApprovalRequest,
    RejectRequest,
    RemediationActionType,
    RemediationStatus,
    RiskLevel,
    UserRole,
)
from app.services.remediation_allowlist import (
    RemediationActionValidator,
    RemediationSecurityError,
    SafeRemediationSimulator,
)
from app.services.remediation_service import RemediationService


# In-memory SQLite fixture for remediation tests
@pytest.fixture
def remediation_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    # Seed required service and test incident
    from app.models.service import Service
    svc = Service(
        id="payment-service",
        name="Payment Service",
        tier="critical",
        owner_team="payments",
    )
    db.add(svc)

    inc = Incident(
        id="INC-TEST-001",
        service_id="payment-service",
        title="High error rate on checkout",
        incident_type="PERFORMANCE",
        severity="SEV2",
        status="INVESTIGATING",
        symptoms="503 errors and connection timeouts",
        root_cause="Connection pool exhaustion",
        resolution="Pending remediation",
        started_at=datetime.now(timezone.utc),
    )
    db.add(inc)
    db.commit()

    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def remediation_client(remediation_db: Session):
    def _override_get_db():
        try:
            yield remediation_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


# =============================================================================
# 1. ALLOWLIST ENFORCEMENT & PARAMETER VALIDATION TESTS
# =============================================================================

def test_allowlist_permits_supported_actions():
    """Verify that all explicit allowlisted actions pass validation with correct parameters."""
    allowed = [
        ("restart_service", "auth-service", {"service_name": "auth-service", "grace_period_seconds": 30}),
        ("scale_service", "api-gateway", {"service_name": "api-gateway", "replicas": 4, "direction": "up"}),
        ("rollback_deployment", "order-service", {"service_name": "order-service", "target_version": "v1.2.0", "target_revision": 2}),
        ("clear_cache", "inventory-service", {"service_name": "inventory-service", "cache_prefix": "cat_"}),
        ("toggle_circuit_breaker", "payment-service", {"service_name": "payment-service", "enabled": True, "failure_threshold": 5}),
    ]
    for action, svc, params in allowed:
        act, validated_params, preview = RemediationActionValidator.validate_action(action, svc, params)
        assert act.value == action
        assert isinstance(validated_params, dict)
        assert len(preview) > 0


def test_allowlist_rejects_arbitrary_actions():
    """Verify that arbitrary or dangerous actions are blocked immediately."""
    dangerous = [
        "execute_bash",
        "run_aws_cli",
        "drop_database",
        "modify_iam_role",
        "delete_namespace",
        "curl_arbitrary_url",
    ]
    for bad_act in dangerous:
        with pytest.raises(RemediationSecurityError) as exc_info:
            RemediationActionValidator.validate_action(bad_act, "api-gateway", {"service_name": "api-gateway"})
        assert "not in the remediation allowlist" in str(exc_info.value).lower()


def test_allowlist_rejects_command_injection_attempts():
    """Verify that shell injection characters or malicious payloads are trapped."""
    injections = [
        ("restart_service", "api-gateway; rm -rf /", {"service_name": "api-gateway; rm -rf /"}),
        ("restart_service", "api-gateway", {"service_name": "api-gateway", "grace_period_seconds": 30, "extra": "$(cat /etc/passwd)"}),
        ("scale_service", "order-service", {"service_name": "order-service", "replicas": 3, "evil": "`whoami`"}),
        ("rollback_deployment", "order-service", {"service_name": "order-service", "target_version": "v1.0; reboot"}),
    ]
    for act, svc, params in injections:
        with pytest.raises(RemediationSecurityError):
            RemediationActionValidator.validate_action(act, svc, params)


def test_parameter_bounds_enforcement():
    """Verify that parameters outside allowable bounds (e.g. replicas > 20) are rejected."""
    # Scale beyond maximum allowable replica ceiling (20)
    with pytest.raises(RemediationSecurityError) as exc:
        RemediationActionValidator.validate_action(
            "scale_service",
            "api-gateway",
            {"service_name": "api-gateway", "replicas": 500},
        )
    assert "validation failed" in str(exc.value).lower()

    # Scale below 1 replica
    with pytest.raises(RemediationSecurityError):
        RemediationActionValidator.validate_action(
            "scale_service",
            "api-gateway",
            {"service_name": "api-gateway", "replicas": 0},
        )


# =============================================================================
# 2. SAFE SIMULATION MODE TESTS
# =============================================================================

def test_safe_simulation_execution():
    """Verify that allowlisted actions execute under safe simulation mode with logs and rollback points."""
    summary = SafeRemediationSimulator.execute_simulation(
        action_type=RemediationActionType.SCALE_SERVICE,
        target_service="order-service",
        parameters={"service_name": "order-service", "replicas": 4, "direction": "up"},
        approved_by="sre-lead@opspilot.io",
    )
    assert summary.simulated is True
    assert summary.validation_passed is True
    assert "Scaled deployment" in summary.output
    assert len(summary.logs) >= 3
    assert summary.rollback_point is not None
    assert summary.execution_duration_ms > 0


# =============================================================================
# 3. AUTHORIZATION BOUNDARY TESTS
# =============================================================================

def test_ai_agent_cannot_approve():
    """CRITICAL SAFETY TEST: AI Agent is strictly forbidden from approving any remediation."""
    with pytest.raises(RemediationAuthorizationError) as exc:
        verify_approval_authorization(UserRole.AI_AGENT, "LOW")
    assert "AI agents are strictly forbidden" in str(exc.value)


def test_viewer_cannot_approve():
    """Verify VIEWER role cannot approve any remediation actions."""
    with pytest.raises(RemediationAuthorizationError) as exc:
        verify_approval_authorization(UserRole.VIEWER, "LOW")
    assert "VIEWER" in str(exc.value)


def test_operator_permission_boundaries():
    """Verify OPERATOR can approve LOW risk, but cannot approve MEDIUM or HIGH risk."""
    # LOW risk permitted
    verify_approval_authorization(UserRole.OPERATOR, "LOW")

    # MEDIUM risk forbidden
    with pytest.raises(RemediationAuthorizationError):
        verify_approval_authorization(UserRole.OPERATOR, "MEDIUM")

    # HIGH risk forbidden
    with pytest.raises(RemediationAuthorizationError):
        verify_approval_authorization(UserRole.OPERATOR, "HIGH")


def test_sre_lead_and_platform_admin_permissions():
    """Verify SRE_LEAD and PLATFORM_ADMIN can approve all risk levels."""
    for role in [UserRole.SRE_LEAD, UserRole.PLATFORM_ADMIN]:
        for risk in ["LOW", "MEDIUM", "HIGH"]:
            verify_approval_authorization(role, risk)


# =============================================================================
# 4. REMEDIATION SERVICE WORKFLOW & AUDIT TRAIL TESTS
# =============================================================================

def test_full_remediation_lifecycle_approval(remediation_db: Session):
    """Test full workflow: RECOMMEND -> APPROVE -> EXECUTE -> SUCCESS -> AUDIT LOG."""
    service = RemediationService()

    # 1. Create recommendation
    rec = service.create_recommendation(
        db=remediation_db,
        incident_id="INC-TEST-001",
        action_type="scale_service",
        target_service="payment-service",
        parameters={"service_name": "payment-service", "replicas": 3, "direction": "up"},
        rationale="Scale payment service to mitigate thread pool exhaustion",
        risk_level="LOW",
    )
    assert rec.status == RemediationStatus.RECOMMENDED.value
    assert rec.id.startswith("REC-")

    # 2. Approve and Execute as SRE_LEAD
    approval_req = ApprovalRequest(
        approved_by="lead-sre@opspilot.io",
        user_role=UserRole.SRE_LEAD,
        comment="Scaling approved after verifying database capacity.",
    )
    updated_rec, audit_log = service.approve_and_execute(
        db=remediation_db,
        recommendation_id=rec.id,
        req=approval_req,
    )

    # 3. Verify Recommendation State
    assert updated_rec.status == RemediationStatus.SUCCESS.value
    assert updated_rec.id == rec.id

    # 4. Verify Audit Log entry
    assert audit_log.status == RemediationStatus.SUCCESS.value
    assert audit_log.recommendation_id == rec.id
    assert audit_log.incident_id == "INC-TEST-001"
    assert audit_log.requested_action == "scale_service"
    assert audit_log.simulation_mode is True
    assert audit_log.user_approval["approved_by"] == "lead-sre@opspilot.io"
    assert audit_log.user_approval["user_role"] == "SRE_LEAD"
    assert audit_log.executor_result["simulated"] is True

    # 5. Verify Incident Updated
    inc = remediation_db.get(Incident, "INC-TEST-001")
    assert inc.status == "MITIGATED"
    assert "executed in safe simulation mode" in inc.resolution


def test_full_remediation_lifecycle_rejection(remediation_db: Session):
    """Test full workflow: RECOMMEND -> REJECT -> AUDIT LOG."""
    service = RemediationService()

    # 1. Create recommendation
    rec = service.create_recommendation(
        db=remediation_db,
        incident_id="INC-TEST-001",
        action_type="rollback_deployment",
        target_service="payment-service",
        parameters={"service_name": "payment-service", "target_version": "v1.1.0", "target_revision": "1"},
        rationale="Rollback payment-service to previous version",
        risk_level="HIGH",
    )

    # 2. Reject as SRE_LEAD
    reject_req = RejectRequest(
        rejected_by="sre-supervisor@opspilot.io",
        user_role=UserRole.SRE_LEAD,
        rejection_reason="Root cause is database deadlocks, not application code regression.",
    )
    rejected_rec, audit_log = service.reject_recommendation(
        db=remediation_db,
        recommendation_id=rec.id,
        req=reject_req,
    )

    # 3. Verify States
    assert rejected_rec.status == RemediationStatus.REJECTED.value
    assert audit_log.status == RemediationStatus.REJECTED.value
    assert audit_log.user_approval["rejected_by"] == "sre-supervisor@opspilot.io"
    assert "Root cause is database deadlocks" in audit_log.user_approval["comment"]

    # 4. Attempting to approve a rejected recommendation should raise error
    with pytest.raises(ValueError) as exc:
        service.approve_and_execute(
            db=remediation_db,
            recommendation_id=rec.id,
            req=ApprovalRequest(approved_by="admin", user_role=UserRole.PLATFORM_ADMIN),
        )
    assert "previously REJECTED" in str(exc.value)


# =============================================================================
# 5. API ENDPOINTS TESTS
# =============================================================================

def test_api_list_recommendations(remediation_client: TestClient, remediation_db: Session):
    """Test GET /api/v1/remediations/recommendations."""
    service = RemediationService()
    service.create_recommendation(
        db=remediation_db,
        incident_id="INC-TEST-001",
        action_type="restart_service",
        target_service="payment-service",
        parameters={"service_name": "payment-service", "grace_period_seconds": 15},
        rationale="Restart payment service pods",
        risk_level="LOW",
    )

    resp = remediation_client.get("/api/v1/remediations/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["action_type"] == "restart_service"
    assert data[0]["status"] == "RECOMMENDED"


def test_api_approve_recommendation(remediation_client: TestClient, remediation_db: Session):
    """Test POST /api/v1/remediations/recommendations/{id}/approve."""
    service = RemediationService()
    rec = service.create_recommendation(
        db=remediation_db,
        incident_id="INC-TEST-001",
        action_type="restart_service",
        target_service="payment-service",
        parameters={"service_name": "payment-service", "grace_period_seconds": 15},
        rationale="Restart payment service pods",
        risk_level="LOW",
    )

    headers = {
        "X-User-Id": "operator-jane@opspilot.io",
        "X-User-Role": "OPERATOR",
    }
    resp = remediation_client.post(
        f"/api/v1/remediations/recommendations/{rec.id}/approve",
        json={"comment": "Approved by Jane for testing"},
        headers=headers,
    )
    assert resp.status_code == 200
    res_json = resp.json()
    assert res_json["status"] == "SUCCESS"


def test_api_ai_agent_blocked_from_approval(remediation_client: TestClient, remediation_db: Session):
    """Test that requests with X-User-Role: AI_AGENT receive 403 Forbidden."""
    service = RemediationService()
    rec = service.create_recommendation(
        db=remediation_db,
        incident_id="INC-TEST-001",
        action_type="restart_service",
        target_service="payment-service",
        parameters={"service_name": "payment-service", "grace_period_seconds": 15},
        rationale="Restart payment service pods",
        risk_level="LOW",
    )

    headers = {
        "X-User-Id": "langgraph-agent",
        "X-User-Role": "AI_AGENT",
    }
    resp = remediation_client.post(
        f"/api/v1/remediations/recommendations/{rec.id}/approve",
        json={"comment": "Automated approval attempt by agent"},
        headers=headers,
    )
    assert resp.status_code == 403
    err_body = resp.json()
    err_msg = err_body.get("error", {}).get("message") or err_body.get("detail", "")
    assert "AI agents are strictly forbidden" in err_msg


def test_api_list_audit_logs(remediation_client: TestClient, remediation_db: Session):
    """Test GET /api/v1/remediations/audit-logs."""
    resp = remediation_client.get("/api/v1/remediations/audit-logs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
