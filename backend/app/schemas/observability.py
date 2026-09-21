from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ===================== Service Schemas =====================
class ServiceBase(BaseModel):
    name: str
    tier: str = "standard"
    owner_team: str = "core-ops"


class ServiceCreate(ServiceBase):
    id: str


class ServiceRead(ServiceBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===================== Metric Schemas =====================
class MetricBase(BaseModel):
    service_id: str
    timestamp: datetime
    cpu_usage: float = Field(..., ge=0.0, le=100.0, description="CPU usage percentage")
    memory_usage: float = Field(..., ge=0.0, le=100.0, description="Memory usage percentage")
    disk_usage: float = Field(..., ge=0.0, le=100.0, description="Disk usage percentage")
    network_traffic_kbps: float = Field(..., ge=0.0, description="Network throughput in KB/s")
    request_count: int = Field(..., ge=0, description="Request count in window")
    latency_p95_ms: float = Field(..., ge=0.0, description="95th percentile latency in ms")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate [0.0 - 1.0]")
    active_connections: int = Field(..., ge=0, description="Active connection count")


class MetricCreate(MetricBase):
    pass


class MetricRead(MetricBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class MetricSummary(BaseModel):
    service_id: str
    sample_count: int
    avg_cpu_usage: float
    max_cpu_usage: float
    avg_memory_usage: float
    max_memory_usage: float
    avg_latency_p95_ms: float
    max_latency_p95_ms: float
    avg_error_rate: float
    max_error_rate: float


# ===================== Log Schemas =====================
class LogBase(BaseModel):
    service_id: str
    timestamp: datetime
    log_level: str
    message: str
    trace_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


class LogCreate(LogBase):
    pass


class LogRead(LogBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ===================== Deployment Schemas =====================
class DeploymentBase(BaseModel):
    service_id: str
    version: str
    deployed_at: datetime
    environment: str = "production"
    status: str = "SUCCESS"
    changelog: Optional[str] = None


class DeploymentCreate(DeploymentBase):
    pass


class DeploymentRead(DeploymentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ===================== Incident Schemas =====================
class IncidentBase(BaseModel):
    service_id: str
    title: str
    started_at: datetime
    resolved_at: Optional[datetime] = None
    severity: str
    symptoms: str
    root_cause: str
    resolution: str
    status: str = "RESOLVED"
    incident_type: str
    related_deployment_id: Optional[int] = None


class IncidentCreate(IncidentBase):
    id: str


class IncidentRead(IncidentBase):
    id: str

    model_config = ConfigDict(from_attributes=True)
