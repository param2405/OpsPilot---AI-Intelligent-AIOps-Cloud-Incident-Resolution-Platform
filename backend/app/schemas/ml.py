"""Pydantic request and response schemas for OpsPilot AI Machine Learning API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ===================== Anomaly Detection Schemas =====================

class MetricTelemetryInput(BaseModel):
    timestamp: Optional[datetime] = None
    cpu_usage: float = Field(..., ge=0.0, le=100.0, description="CPU utilization percentage")
    memory_usage: float = Field(..., ge=0.0, le=100.0, description="Memory utilization percentage")
    disk_usage: float = Field(..., ge=0.0, le=100.0, description="Disk utilization percentage")
    network_traffic_kbps: float = Field(..., ge=0.0, description="Network throughput in KB/s")
    request_count: int = Field(..., ge=0, description="Window request count")
    latency_p95_ms: float = Field(..., ge=0.0, description="95th percentile latency in ms")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate [0.0 - 1.0]")
    active_connections: int = Field(..., ge=0, description="Concurrent socket connections")


class AnomalyDetectionRequest(MetricTelemetryInput):
    service_id: str = Field(..., description="Monitored service ID")
    recent_history: Optional[List[MetricTelemetryInput]] = Field(
        None,
        description="Optional recent telemetry buffer (ordered oldest to newest) for rolling stats",
    )


class AnomalyDetectionResponse(BaseModel):
    service_id: str
    timestamp: datetime
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated anomaly score [0.0 - 1.0]")
    is_anomaly: bool = Field(..., description="Binary anomaly indicator flag")
    contributing_signals: List[str] = Field(default_factory=list, description="Top deviating metric features")
    model_version: str
    algorithm: str


# ===================== Incident Classification Schemas =====================

class IncidentClassificationRequest(BaseModel):
    title: str = Field(..., description="Operational incident title")
    symptoms: str = Field(..., description="Detailed technical symptoms and error outputs")
    service_id: Optional[str] = Field(None, description="Affected microservice ID")
    tier: Optional[str] = Field("standard", description="Service tier (standard, high, critical)")
    cpu_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    memory_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    disk_usage: Optional[float] = Field(None, ge=0.0, le=100.0)
    network_traffic_kbps: Optional[float] = Field(None, ge=0.0)
    request_count: Optional[int] = Field(None, ge=0)
    latency_p95_ms: Optional[float] = Field(None, ge=0.0)
    error_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    active_connections: Optional[int] = Field(None, ge=0)


class IncidentClassificationResponse(BaseModel):
    category: str = Field(..., description="Predicted failure domain (database, application, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model prediction confidence")
    probabilities: Dict[str, float] = Field(..., description="Class probability distribution")
    model_version: str
    algorithm: str


# ===================== Incident Severity Schemas =====================

class SeverityPredictionRequest(IncidentClassificationRequest):
    pass


class SeverityPredictionResponse(BaseModel):
    severity: str = Field(..., description="Predicted severity (LOW, MEDIUM, HIGH, CRITICAL)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model prediction confidence")
    probabilities: Dict[str, float] = Field(..., description="Severity class distribution")
    risk_factors: List[str] = Field(default_factory=list, description="Primary drivers of severity rating")
    model_version: str
    algorithm: str


# ===================== Registry & Retrain Schemas =====================

class ModelVersionDetail(BaseModel):
    model_name: str
    active_version: str
    algorithm: str
    created_at: Optional[str] = None
    mlflow_run_id: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)


class ModelsOverviewResponse(BaseModel):
    models: Dict[str, Any]


class RetrainRequest(BaseModel):
    model: str = Field("all", description="Model to retrain ('all', 'anomaly', 'classification', 'severity')")
    version: Optional[str] = Field(None, description="Custom version string (e.g. 'v1.1.0')")


class RetrainResponse(BaseModel):
    status: str
    message: str
    results: Dict[str, Any]
