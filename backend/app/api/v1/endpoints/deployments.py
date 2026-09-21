from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.observability_repo import ObservabilityRepository
from app.schemas.observability import DeploymentRead

router = APIRouter(prefix="/deployments", tags=["Deployments"])


@router.get("", response_model=List[DeploymentRead])
def get_deployments(
    service_id: Optional[str] = Query(None, description="Filter by service ID"),
    environment: Optional[str] = Query(None, description="Filter by environment (production, staging)"),
    status: Optional[str] = Query(None, description="Filter by status (SUCCESS, FAILED, ROLLED_BACK)"),
    limit: int = Query(50, ge=1, le=500, description="Max deployments to return"),
    db: Session = Depends(get_db),
) -> List[DeploymentRead]:
    """Retrieve historical deployment events and rollout statuses."""
    deployments = ObservabilityRepository.query_deployments(
        db=db,
        service_id=service_id,
        environment=environment,
        status=status,
        limit=limit,
    )
    return [DeploymentRead.model_validate(d) for d in deployments]
