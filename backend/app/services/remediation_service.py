"""Service implementing the Phase 9 Human-In-The-Loop Remediation Workflow & Audit Logging."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security_remediation import verify_approval_authorization
from app.models.incident import Incident
from app.models.remediation import RemediationAuditLog, RemediationRecommendation
from app.schemas.remediation import (
    ApprovalRequest,
    ExecutionResultSummary,
    RejectRequest,
    RemediationActionType,
    RemediationAuditLogResponse,
    RemediationRecommendationResponse,
    RemediationStatus,
    SimulateRemediationRequest,
    UserRole,
)
from app.services.remediation_allowlist import (
    RemediationActionValidator,
    RemediationSecurityError,
    SafeRemediationSimulator,
)

logger = logging.getLogger(__name__)


class RemediationService:
    """Manages recommendation generation, human approvals, allowlist enforcement, and audit logs."""

    @staticmethod
    def _generate_id(prefix: str) -> str:
        timestamp_part = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        unique_part = uuid.uuid4().hex[:6].upper()
        return f"{prefix}-{timestamp_part}-{unique_part}"

    def create_recommendation(
        self,
        db: Session,
        incident_id: str,
        action_type: str,
        target_service: str,
        parameters: Dict[str, Any],
        rationale: str,
        risk_level: str = "LOW",
        investigation_id: Optional[str] = None,
        runbook_reference: Optional[str] = None,
    ) -> RemediationRecommendation:
        """Create a new allowlisted remediation recommendation awaiting human approval."""
        # Pre-validate against allowlist to reject non-allowlisted actions upfront
        validated_action, validated_params, preview = RemediationActionValidator.validate_action(
            action_type_str=action_type,
            target_service=target_service,
            parameters=parameters,
        )

        rec = RemediationRecommendation(
            id=self._generate_id("REC"),
            incident_id=incident_id,
            investigation_id=investigation_id,
            action_type=validated_action.value,
            target_service=target_service,
            parameters=validated_params,
            rationale=rationale,
            risk_level=risk_level.upper(),
            status=RemediationStatus.RECOMMENDED.value,
            command_preview=preview,
            runbook_reference=runbook_reference,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        logger.info(
            "Created remediation recommendation '%s' for incident '%s' (action: %s, risk: %s)",
            rec.id, incident_id, rec.action_type, rec.risk_level
        )
        return rec

    def list_recommendations(
        self,
        db: Session,
        incident_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[RemediationRecommendationResponse]:
        """List recommendations with optional filters."""
        stmt = select(RemediationRecommendation).order_by(desc(RemediationRecommendation.created_at)).limit(limit)
        if incident_id:
            stmt = stmt.where(RemediationRecommendation.incident_id == incident_id)
        if status:
            stmt = stmt.where(RemediationRecommendation.status == status.upper())

        rows = db.scalars(stmt).all()
        return [RemediationRecommendationResponse.model_validate(r) for r in rows]

    def get_recommendation(self, db: Session, recommendation_id: str) -> RemediationRecommendation:
        """Fetch single recommendation by ID or raise ValueError."""
        stmt = select(RemediationRecommendation).where(RemediationRecommendation.id == recommendation_id)
        rec = db.scalar(stmt)
        if not rec:
            raise ValueError(f"Remediation recommendation '{recommendation_id}' not found.")
        return rec

    def approve_and_execute(
        self,
        db: Session,
        recommendation_id: str,
        req: ApprovalRequest,
    ) -> tuple[RemediationRecommendationResponse, RemediationAuditLogResponse]:
        """Approve and execute an allowlisted recommendation under Safe Simulation Mode.
        
        WORKFLOW:
        1. Verify authorization boundary (human role vs action risk level).
        2. Validate action against allowlist and strict parameter bounds.
        3. Transition status: RECOMMENDED -> APPROVED -> EXECUTING.
        4. Execute safe simulation mode.
        5. Record complete audit log with user approval details and executor output.
        6. Update incident state in database.
        """
        rec = self.get_recommendation(db=db, recommendation_id=recommendation_id)

        if rec.status in (RemediationStatus.SUCCESS.value, RemediationStatus.APPROVED.value, RemediationStatus.EXECUTING.value):
            raise ValueError(f"Recommendation '{recommendation_id}' is already in state '{rec.status}'.")
        if rec.status == RemediationStatus.REJECTED.value:
            raise ValueError(f"Recommendation '{recommendation_id}' was previously REJECTED.")

        # 1. Authorization boundary check
        verify_approval_authorization(user_role=req.user_role, risk_level=rec.risk_level)

        # 2. Strict allowlist and parameter bounds validation
        validated_action, validated_params, _ = RemediationActionValidator.validate_action(
            action_type_str=rec.action_type,
            target_service=rec.target_service,
            parameters=rec.parameters,
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        rec.status = RemediationStatus.APPROVED.value
        rec.updated_at = datetime.now(timezone.utc)
        db.commit()

        # 3. Transition to EXECUTING
        rec.status = RemediationStatus.EXECUTING.value
        db.commit()

        # 4. Execute Safe Simulation Mode
        try:
            exec_summary = SafeRemediationSimulator.execute_simulation(
                action_type=validated_action,
                target_service=rec.target_service,
                parameters=validated_params,
                approved_by=req.approved_by,
            )
            final_status = RemediationStatus.SUCCESS.value
            rec.status = RemediationStatus.SUCCESS.value
        except Exception as exc:
            logger.exception("Error executing remediation simulation for '%s': %s", rec.id, exc)
            final_status = RemediationStatus.FAILED.value
            rec.status = RemediationStatus.FAILED.value
            exec_summary = ExecutionResultSummary(
                output=f"Simulation failed: {str(exc)}",
                execution_duration_ms=10.0,
                simulated=True,
                validation_passed=False,
                logs=[f"[EXECUTION-ERROR] {str(exc)}"],
                rollback_point=None,
            )

        # 5. Create immutable Audit Log
        audit_log = RemediationAuditLog(
            id=self._generate_id("AUD"),
            recommendation_id=rec.id,
            incident_id=rec.incident_id,
            requested_action=rec.action_type,
            action_parameters=rec.parameters,
            simulation_mode=True,
            user_approval={
                "approved_by": req.approved_by,
                "user_role": req.user_role.value,
                "approved_at": now_iso,
                "comment": req.comment,
                "approval_status": "APPROVED",
            },
            executor_result=exec_summary.model_dump(),
            status=final_status,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit_log)

        # 6. Update Incident Lifecycle State
        incident_stmt = select(Incident).where(Incident.id == rec.incident_id)
        incident = db.scalar(incident_stmt)
        if incident and final_status == RemediationStatus.SUCCESS.value:
            if incident.status in ("INVESTIGATING", "IDENTIFIED"):
                incident.status = "MITIGATED"
                incident.mitigated_at = datetime.now(timezone.utc)
            incident.resolution = (
                f"Remediation '{rec.action_type}' executed in safe simulation mode by {req.approved_by} ({req.user_role.value}). "
                f"Result: {exec_summary.output}"
            )

        db.commit()
        db.refresh(rec)
        db.refresh(audit_log)

        logger.info(
            "Remediation '%s' approved and executed successfully by '%s'. Audit log: '%s'",
            rec.id, req.approved_by, audit_log.id
        )

        return (
            RemediationRecommendationResponse.model_validate(rec),
            RemediationAuditLogResponse.model_validate(audit_log),
        )

    def reject_recommendation(
        self,
        db: Session,
        recommendation_id: str,
        req: RejectRequest,
    ) -> tuple[RemediationRecommendationResponse, RemediationAuditLogResponse]:
        """Reject a remediation recommendation and record reason in immutable audit log."""
        rec = self.get_recommendation(db=db, recommendation_id=recommendation_id)

        if rec.status == RemediationStatus.SUCCESS.value:
            raise ValueError(f"Cannot reject recommendation '{recommendation_id}': action was already executed.")

        if req.user_role in (UserRole.AI_AGENT, UserRole.VIEWER):
            raise ValueError(f"Role '{req.user_role}' is not authorized to reject recommendations.")

        rec.status = RemediationStatus.REJECTED.value
        rec.updated_at = datetime.now(timezone.utc)

        audit_log = RemediationAuditLog(
            id=self._generate_id("AUD"),
            recommendation_id=rec.id,
            incident_id=rec.incident_id,
            requested_action=rec.action_type,
            action_parameters=rec.parameters,
            simulation_mode=True,
            user_approval={
                "rejected_by": req.rejected_by,
                "user_role": req.user_role.value,
                "rejection_reason": req.rejection_reason,
                "comment": req.rejection_reason,
                "rejected_at": datetime.now(timezone.utc).isoformat(),
                "approval_status": "REJECTED",
            },
            executor_result={
                "output": f"Action rejected by {req.rejected_by}: {req.rejection_reason}",
                "execution_duration_ms": 0.0,
                "simulated": True,
                "validation_passed": True,
                "logs": [f"[REJECTION] Operator rejected action: {req.rejection_reason}"],
            },
            status=RemediationStatus.REJECTED.value,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit_log)
        db.commit()
        db.refresh(rec)
        db.refresh(audit_log)

        logger.info(
            "Recommendation '%s' rejected by '%s' with reason: %s",
            rec.id, req.rejected_by, req.rejection_reason
        )

        return (
            RemediationRecommendationResponse.model_validate(rec),
            RemediationAuditLogResponse.model_validate(audit_log),
        )

    def list_audit_logs(
        self,
        db: Session,
        incident_id: Optional[str] = None,
        recommendation_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[RemediationAuditLogResponse]:
        """Query immutable audit logs."""
        stmt = select(RemediationAuditLog).order_by(desc(RemediationAuditLog.timestamp)).limit(limit)
        if incident_id:
            stmt = stmt.where(RemediationAuditLog.incident_id == incident_id)
        if recommendation_id:
            stmt = stmt.where(RemediationAuditLog.recommendation_id == recommendation_id)

        rows = db.scalars(stmt).all()
        return [RemediationAuditLogResponse.model_validate(r) for r in rows]

    def simulate_direct_action(
        self,
        db: Session,
        req: SimulateRemediationRequest,
    ) -> RemediationAuditLogResponse:
        """Simulate an allowlisted action directly with human operator authorization."""
        verify_approval_authorization(user_role=req.user_role, risk_level="LOW")

        validated_action, validated_params, _ = RemediationActionValidator.validate_action(
            action_type_str=req.action_type.value,
            target_service=req.target_service,
            parameters=req.parameters,
        )

        # Temporary or ad-hoc recommendation record for tracking
        rec = RemediationRecommendation(
            id=self._generate_id("REC-ADHOC"),
            incident_id=req.incident_id or "INC-ADHOC",
            action_type=validated_action.value,
            target_service=req.target_service,
            parameters=validated_params,
            rationale=f"Direct operator execution by {req.authorized_by}",
            risk_level="LOW",
            status=RemediationStatus.SUCCESS.value,
        )
        db.add(rec)
        db.commit()

        exec_summary = SafeRemediationSimulator.execute_simulation(
            action_type=validated_action,
            target_service=req.target_service,
            parameters=validated_params,
            approved_by=req.authorized_by,
        )

        audit_log = RemediationAuditLog(
            id=self._generate_id("AUD"),
            recommendation_id=rec.id,
            incident_id=req.incident_id or "INC-ADHOC",
            requested_action=validated_action.value,
            action_parameters=validated_params,
            simulation_mode=True,
            user_approval={
                "approved_by": req.authorized_by,
                "user_role": req.user_role.value,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approval_status": "APPROVED",
            },
            executor_result=exec_summary.model_dump(),
            status=RemediationStatus.SUCCESS.value,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return RemediationAuditLogResponse.model_validate(audit_log)
