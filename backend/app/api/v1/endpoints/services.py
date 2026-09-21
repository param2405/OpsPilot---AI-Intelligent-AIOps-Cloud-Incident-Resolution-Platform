from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.observability_repo import ObservabilityRepository
from app.schemas.observability import ServiceRead

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("", response_model=List[ServiceRead])
def list_services(db: Session = Depends(get_db)) -> List[ServiceRead]:
    """Retrieve all registered services in the system."""
    services = ObservabilityRepository.list_services(db)
    return [ServiceRead.model_validate(s) for s in services]


@router.get("/{service_id}", response_model=ServiceRead)
def get_service(service_id: str, db: Session = Depends(get_db)) -> ServiceRead:
    """Retrieve service metadata by service ID."""
    service = ObservabilityRepository.get_service(db, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with id '{service_id}' not found",
        )
    return ServiceRead.model_validate(service)
