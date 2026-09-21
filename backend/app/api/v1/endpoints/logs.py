from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.observability_repo import ObservabilityRepository
from app.schemas.observability import LogRead

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("", response_model=List[LogRead])
def get_logs(
    service_id: Optional[str] = Query(None, description="Filter logs by service ID"),
    log_level: Optional[str] = Query(None, description="Filter logs by level (DEBUG, INFO, WARN, ERROR, FATAL)"),
    trace_id: Optional[str] = Query(None, description="Filter logs by distributed trace ID"),
    search: Optional[str] = Query(None, description="Case-insensitive substring search in log message"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (ISO 8601)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (ISO 8601)"),
    limit: int = Query(100, ge=1, le=1000, description="Max logs to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
) -> List[LogRead]:
    """Retrieve structured operational logs with flexible filtering and trace correlation."""
    logs = ObservabilityRepository.query_logs(
        db=db,
        service_id=service_id,
        log_level=log_level,
        trace_id=trace_id,
        search=search,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
    )
    return [LogRead.model_validate(log) for log in logs]
