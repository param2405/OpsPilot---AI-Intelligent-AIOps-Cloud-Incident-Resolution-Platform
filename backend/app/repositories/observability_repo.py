from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.deployment import Deployment
from app.models.incident import Incident
from app.models.log import LogEntry
from app.models.metric import Metric
from app.models.service import Service
from app.schemas.observability import (
    DeploymentCreate,
    IncidentCreate,
    LogCreate,
    MetricCreate,
    MetricSummary,
    ServiceCreate,
)


class ObservabilityRepository:
    """Encapsulates data access and filtering queries for observability entities."""

    # ===================== Service Operations =====================
    @staticmethod
    def list_services(db: Session) -> List[Service]:
        stmt = select(Service).order_by(Service.name)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_service(db: Session, service_id: str) -> Optional[Service]:
        return db.get(Service, service_id)

    @staticmethod
    def create_service(db: Session, service_in: ServiceCreate) -> Service:
        service = Service(
            id=service_in.id,
            name=service_in.name,
            tier=service_in.tier,
            owner_team=service_in.owner_team,
        )
        db.add(service)
        db.commit()
        db.refresh(service)
        return service

    # ===================== Metric Operations =====================
    @staticmethod
    def query_metrics(
        db: Session,
        service_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Metric]:
        stmt = select(Metric)
        if service_id:
            stmt = stmt.where(Metric.service_id == service_id)
        if start_time:
            stmt = stmt.where(Metric.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(Metric.timestamp <= end_time)
        stmt = stmt.order_by(desc(Metric.timestamp)).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_metrics_summary(
        db: Session,
        service_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Optional[MetricSummary]:
        stmt = (
            select(
                func.count(Metric.id).label("sample_count"),
                func.coalesce(func.avg(Metric.cpu_usage), 0.0).label("avg_cpu"),
                func.coalesce(func.max(Metric.cpu_usage), 0.0).label("max_cpu"),
                func.coalesce(func.avg(Metric.memory_usage), 0.0).label("avg_mem"),
                func.coalesce(func.max(Metric.memory_usage), 0.0).label("max_mem"),
                func.coalesce(func.avg(Metric.latency_p95_ms), 0.0).label("avg_latency"),
                func.coalesce(func.max(Metric.latency_p95_ms), 0.0).label("max_latency"),
                func.coalesce(func.avg(Metric.error_rate), 0.0).label("avg_err"),
                func.coalesce(func.max(Metric.error_rate), 0.0).label("max_err"),
            )
            .where(Metric.service_id == service_id)
        )
        if start_time:
            stmt = stmt.where(Metric.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(Metric.timestamp <= end_time)

        row = db.execute(stmt).one()
        if not row.sample_count:
            return None

        return MetricSummary(
            service_id=service_id,
            sample_count=int(row.sample_count),
            avg_cpu_usage=round(float(row.avg_cpu), 2),
            max_cpu_usage=round(float(row.max_cpu), 2),
            avg_memory_usage=round(float(row.avg_mem), 2),
            max_memory_usage=round(float(row.max_mem), 2),
            avg_latency_p95_ms=round(float(row.avg_latency), 2),
            max_latency_p95_ms=round(float(row.max_latency), 2),
            avg_error_rate=round(float(row.avg_err), 4),
            max_error_rate=round(float(row.max_err), 4),
        )

    # ===================== Log Operations =====================
    @staticmethod
    def query_logs(
        db: Session,
        service_id: Optional[str] = None,
        log_level: Optional[str] = None,
        trace_id: Optional[str] = None,
        search: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[LogEntry]:
        stmt = select(LogEntry)
        if service_id:
            stmt = stmt.where(LogEntry.service_id == service_id)
        if log_level:
            stmt = stmt.where(LogEntry.log_level == log_level.upper())
        if trace_id:
            stmt = stmt.where(LogEntry.trace_id == trace_id)
        if search:
            stmt = stmt.where(LogEntry.message.ilike(f"%{search}%"))
        if start_time:
            stmt = stmt.where(LogEntry.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(LogEntry.timestamp <= end_time)
        stmt = stmt.order_by(desc(LogEntry.timestamp)).offset(offset).limit(limit)
        return list(db.scalars(stmt).all())

    # ===================== Deployment Operations =====================
    @staticmethod
    def query_deployments(
        db: Session,
        service_id: Optional[str] = None,
        environment: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Deployment]:
        stmt = select(Deployment)
        if service_id:
            stmt = stmt.where(Deployment.service_id == service_id)
        if environment:
            stmt = stmt.where(Deployment.environment == environment)
        if status:
            stmt = stmt.where(Deployment.status == status.upper())
        stmt = stmt.order_by(desc(Deployment.deployed_at)).limit(limit)
        return list(db.scalars(stmt).all())

    # ===================== Incident Operations =====================
    @staticmethod
    def query_incidents(
        db: Session,
        service_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        incident_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Incident]:
        stmt = select(Incident)
        if service_id:
            stmt = stmt.where(Incident.service_id == service_id)
        if severity:
            stmt = stmt.where(Incident.severity == severity.upper())
        if status:
            stmt = stmt.where(Incident.status == status.upper())
        if incident_type:
            stmt = stmt.where(Incident.incident_type == incident_type.upper())
        stmt = stmt.order_by(desc(Incident.started_at)).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get_incident(db: Session, incident_id: str) -> Optional[Incident]:
        return db.get(Incident, incident_id)
