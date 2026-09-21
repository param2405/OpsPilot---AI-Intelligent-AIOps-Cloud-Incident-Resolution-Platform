from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.observability_repo import ObservabilityRepository
from app.schemas.observability import MetricRead, MetricSummary

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("", response_model=List[MetricRead])
def get_metrics(
    service_id: Optional[str] = Query(None, description="Filter metrics by service ID"),
    start_time: Optional[datetime] = Query(None, description="Filter metrics after this timestamp (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="Filter metrics before this timestamp (ISO 8601)"),
    limit: int = Query(100, ge=1, le=5000, description="Max number of metric points to return"),
    db: Session = Depends(get_db),
) -> List[MetricRead]:
    """Retrieve time-series telemetry metrics filtered by service and time window."""
    metrics = ObservabilityRepository.query_metrics(
        db=db,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return [MetricRead.model_validate(m) for m in metrics]


@router.get("/summary", response_model=MetricSummary)
def get_metrics_summary(
    service_id: str = Query(..., description="Service ID to summarize"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (ISO 8601)"),
    db: Session = Depends(get_db),
) -> MetricSummary:
    """Retrieve aggregate telemetry statistics (avg/max CPU, memory, latency, error rate) for a service."""
    summary = ObservabilityRepository.get_metrics_summary(
        db=db,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
    )
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No metrics found for service '{service_id}' in the given time window",
        )
    return summary
