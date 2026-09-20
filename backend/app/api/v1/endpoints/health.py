from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse, ReadinessResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


def get_health_service(settings: Settings = Depends(get_settings)) -> HealthService:
    return HealthService(settings)


@router.get("/health", response_model=HealthResponse)
def health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    """Liveness: process is up. Does not query PostgreSQL."""
    return service.liveness()


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(
    db: Session = Depends(get_db),
    service: HealthService = Depends(get_health_service),
) -> ReadinessResponse | JSONResponse:
    """Readiness: process is up and PostgreSQL accepts connections."""
    payload = service.readiness(db)
    if payload.status != "ready":
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload
