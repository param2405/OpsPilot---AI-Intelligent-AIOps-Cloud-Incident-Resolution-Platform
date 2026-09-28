"""FastAPI endpoints for Phase 7: Intelligent Incident Orchestration Pipeline."""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.orchestration import (
    IncidentInvestigationResponse,
    InvestigationSummary,
    ManualInvestigateRequest,
    PipelineHealthStatusResponse,
    TelemetryIngestRequest,
)
from app.services.orchestration_service import IncidentOrchestrationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestration", tags=["Incident Orchestration Pipeline"])

# Shared service singleton
_orchestration_service: Optional[IncidentOrchestrationService] = None


def get_orchestration_service() -> IncidentOrchestrationService:
    global _orchestration_service
    if _orchestration_service is None:
        _orchestration_service = IncidentOrchestrationService()
    return _orchestration_service


@router.post(
    "/process-telemetry",
    response_model=IncidentInvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest telemetry and execute end-to-end incident orchestration pipeline",
)
def process_telemetry(
    payload: TelemetryIngestRequest,
    db: Session = Depends(get_db),
    service: IncidentOrchestrationService = Depends(get_orchestration_service),
) -> IncidentInvestigationResponse:
    """Execute the complete 12-step intelligent incident orchestration pipeline:
    
    1. Receive observability telemetry
    2. Run deterministic ML anomaly detection
    3. If anomaly threshold is crossed, correlate or create incident in DB
    4. Run deterministic ML failure classification
    5. Run deterministic ML severity prediction
    6. Analyze relevant log sequences with PyTorch deep learning sequence model
    7. Assemble context for LangGraph agent
    8. Agent investigates using read-only diagnostic tools
    9. RAG retrieves relevant runbooks, guides, and historical postmortems
    10. LLM / Grounded generator synthesizes root cause (preserving deterministic ML)
    11. Store full investigation record in DB and update incident state
    12. Expose and return the complete diagnostic incident state
    """
    try:
        return service.process_telemetry(payload=payload, db=db)
    except Exception as exc:
        logger.exception("Error executing telemetry orchestration pipeline: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incident orchestration pipeline error: {str(exc)}",
        )


@router.post(
    "/investigate",
    response_model=IncidentInvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger full orchestration investigation on an existing incident",
)
def investigate_existing_incident(
    req: ManualInvestigateRequest,
    db: Session = Depends(get_db),
    service: IncidentOrchestrationService = Depends(get_orchestration_service),
) -> IncidentInvestigationResponse:
    """Trigger the full orchestration pipeline for an existing incident ID."""
    try:
        return service.investigate_incident_by_id(req=req, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Error investigating incident '%s': %s", req.incident_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation failed: {str(exc)}",
        )


@router.get(
    "/investigations/{id_param}",
    response_model=IncidentInvestigationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve full investigation record by investigation ID or incident ID",
)
def get_investigation_by_id(
    id_param: str,
    db: Session = Depends(get_db),
    service: IncidentOrchestrationService = Depends(get_orchestration_service),
) -> IncidentInvestigationResponse:
    """Fetch complete diagnostic state for an investigation or incident."""
    res = service.get_investigation(investigation_id_or_incident_id=id_param, db=db)
    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No investigation record found for '{id_param}'",
        )
    return res


@router.get(
    "/investigations",
    response_model=List[InvestigationSummary],
    status_code=status.HTTP_200_OK,
    summary="List past incident investigations",
)
def list_investigations(
    service_id: Optional[str] = Query(None, description="Filter by service ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (COMPLETED, INSUFFICIENT_EVIDENCE, DEGRADED, NORMAL)"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    service: IncidentOrchestrationService = Depends(get_orchestration_service),
) -> List[InvestigationSummary]:
    """Retrieve historical investigation runs with status, category, and severity ratings."""
    return service.list_investigations(db=db, service_id=service_id, status=status_filter, limit=limit)


@router.get(
    "/pipeline/status",
    response_model=PipelineHealthStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check health and readiness of all orchestration pipeline components",
)
def get_pipeline_status(
    service: IncidentOrchestrationService = Depends(get_orchestration_service),
) -> PipelineHealthStatusResponse:
    """Verify active health, versions, and readiness across ML, DL, Agent, and RAG components."""
    return service.get_pipeline_health()
