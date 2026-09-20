from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.health import DatabaseCheck, HealthResponse, ReadinessResponse

logger = get_logger(__name__)

API_VERSION = "0.1.0"


class HealthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def liveness(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=self._settings.app_name,
            environment=self._settings.environment,
            version=API_VERSION,
        )

    def readiness(self, db: Session) -> ReadinessResponse:
        database = self._check_database(db)
        status = "ready" if database.connected else "unavailable"
        return ReadinessResponse(
            status=status,
            service=self._settings.app_name,
            environment=self._settings.environment,
            version=API_VERSION,
            database=database,
        )

    def _check_database(self, db: Session) -> DatabaseCheck:
        try:
            db.execute(text("SELECT 1"))
            return DatabaseCheck(connected=True, detail="PostgreSQL accepted SELECT 1.")
        except SQLAlchemyError as exc:
            logger.warning("Readiness database check failed: %s", exc)
            return DatabaseCheck(connected=False, detail="PostgreSQL is not reachable.")
