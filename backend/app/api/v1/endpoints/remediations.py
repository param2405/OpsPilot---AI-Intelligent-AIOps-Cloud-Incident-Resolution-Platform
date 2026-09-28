"""FastAPI endpoints for Phase 9: Human-In-The-Loop Remediation & Security Audit Logs."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security_remediation import (
    RemediationAuthorizationError,
    get_authenticated_user_context,
)
from app.db.session import get_db
from app.schemas.remediation import (
    ApprovalRequest,
    RejectRequest,
    RemediationAuditLogResponse,
    RemediationRecommendationResponse,
    SimulateRemediationRequest,
    UserRole,
)
from app.services.remediation_allowlist import RemediationSecurityError
from app.services.remediation_service import RemediationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remediations", tags=["Human-In-The-Loop Remediation"])

_remediation_service: Optional[RemediationService] = None


def get_remediation_service() -> RemediationService:
    global _remediation_service
    if _remediation_service is None:
        _remediation_service = RemediationService()
    return _remediation_service


@router.get(
    "/recommendations",
    response_model=List[RemediationRecommendationResponse],
    status_code=status.HTTP_200_OK,
    summary="List remediation recommendations awaiting or processed through human approval",
)
def list_recommendations(
    incident_id: Optional[str] = Query(None, description="Filter by incident ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (RECOMMENDED, APPROVED, EXECUTING, SUCCESS, FAILED, REJECTED)"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    service: RemediationService = Depends(get_remediation_service),
) -> List[RemediationRecommendationResponse]:
    """Retrieve all remediation recommendations."""
    return service.list_recommendations(db=db, incident_id=incident_id, status=status_filter, limit=limit)


@router.get(
    "/recommendations/{rec_id}",
    response_model=RemediationRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get remediation recommendation details by ID",
)
def get_recommendation_details(
    rec_id: str,
    db: Session = Depends(get_db),
    service: RemediationService = Depends(get_remediation_service),
) -> RemediationRecommendationResponse:
    """Fetch single recommendation by ID."""
    try:
        rec = service.get_recommendation(db=db, recommendation_id=rec_id)
        return RemediationRecommendationResponse.model_validate(rec)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/recommendations/{rec_id}/approve",
    response_model=RemediationRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Human approval and safe simulation execution of an allowlisted recommendation",
)
def approve_recommendation(
    rec_id: str,
    payload: Optional[ApprovalRequest] = None,
    user_context: tuple[str, UserRole] = Depends(get_authenticated_user_context),
    db: Session = Depends(get_db),
    service: RemediationService = Depends(get_remediation_service),
) -> RemediationRecommendationResponse:
    """Approve a recommendation.
    
    CRITICAL SAFETY RULES:
    1. Verifies authorization boundary (AI Agent cannot approve).
    2. Validates action against strict explicit allowlist.
    3. Executes strictly in Safe Simulation Mode (no arbitrary shell or AWS actions).
    4. Records immutable entry in audit log.
    5. Updates incident lifecycle state.
    """
    user_id, user_role = user_context
    if payload is None:
        req = ApprovalRequest(
            approved_by=user_id,
            user_role=user_role,
            comment="Approved via OpsPilot Human-In-The-Loop Console",
        )
    else:
        req = ApprovalRequest(
            approved_by=payload.approved_by or user_id,
            user_role=payload.user_role or user_role,
            comment=payload.comment or "Approved via OpsPilot Human-In-The-Loop Console",
        )

    try:
        updated_rec, _ = service.approve_and_execute(db=db, recommendation_id=rec_id, req=req)
        return updated_rec
    except RemediationAuthorizationError:
        raise
    except RemediationSecurityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error approving recommendation '%s': %s", rec_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post(
    "/recommendations/{rec_id}/reject",
    response_model=RemediationRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Human rejection of a remediation recommendation with rationale logged to audit trail",
)
def reject_recommendation(
    rec_id: str,
    payload: RejectRequest,
    db: Session = Depends(get_db),
    service: RemediationService = Depends(get_remediation_service),
) -> RemediationRecommendationResponse:
    """Reject a recommendation, recording the rationale in the audit log."""
    try:
        updated_rec, _ = service.reject_recommendation(db=db, recommendation_id=rec_id, req=payload)
        return updated_rec
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error rejecting recommendation '%s': %s", rec_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/audit-logs",
    response_model=List[RemediationAuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="View complete remediation history and immutable security audit logs",
)
def list_audit_logs(
    incident_id: Optional[str] = Query(None, description="Filter audit logs by incident ID"),
    recommendation_id: Optional[str] = Query(None, description="Filter audit logs by recommendation ID"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    service: RemediationService = Depends(get_remediation_service),
) -> List[RemediationAuditLogResponse]:
    """Retrieve immutable audit logs tracking operator approvals, execution results, and rejections."""
    return service.list_audit_logs(
        db=db,
        incident_id=incident_id,
        recommendation_id=recommendation_id,
        limit=limit,
    )


@router.post(
    "/simulate",
    response_model=RemediationAuditLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Directly test an allowlisted remediation action in Safe Simulation Mode",
)
def simulate_action(
    req: SimulateRemediationRequest,
    db: Session = Depends(get_db),
    service: RemediationService = Depends(get_remediation_service),
) -> RemediationAuditLogResponse:
    """Simulate allowlisted action directly under operator authorization."""
    try:
        return service.simulate_direct_action(db=db, req=req)
    except RemediationAuthorizationError:
        raise
    except RemediationSecurityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.exception("Error simulating direct action: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
