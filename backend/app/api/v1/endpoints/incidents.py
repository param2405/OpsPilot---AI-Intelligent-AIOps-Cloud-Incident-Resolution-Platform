from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.observability_repo import ObservabilityRepository
from app.schemas.observability import IncidentRead

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get("", response_model=List[IncidentRead])
def get_incidents(
    service_id: Optional[str] = Query(None, description="Filter incidents by service ID"),
    severity: Optional[str] = Query(None, description="Filter by severity (P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW)"),
    status: Optional[str] = Query(None, description="Filter by lifecycle status (INVESTIGATING, IDENTIFIED, MITIGATED, RESOLVED)"),
    incident_type: Optional[str] = Query(None, description="Filter by incident pattern type"),
    limit: int = Query(50, ge=1, le=200, description="Max incidents to return"),
    db: Session = Depends(get_db),
) -> List[IncidentRead]:
    """Retrieve incidents with filtering across severity, status, and failure category."""
    incidents = ObservabilityRepository.query_incidents(
        db=db,
        service_id=service_id,
        severity=severity,
        status=status,
        incident_type=incident_type,
        limit=limit,
    )
    return [IncidentRead.model_validate(i) for i in incidents]


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident_by_id(incident_id: str, db: Session = Depends(get_db)) -> IncidentRead:
    """Retrieve full engineering details of a specific incident including symptoms, root cause, and resolution."""
    incident = ObservabilityRepository.get_incident(db, incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return IncidentRead.model_validate(incident)
