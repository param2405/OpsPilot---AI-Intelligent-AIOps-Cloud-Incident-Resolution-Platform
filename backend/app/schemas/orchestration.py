"""Pydantic schemas for Phase 7: Intelligent Incident Orchestration Pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import EvidenceItem, HistoricalIncidentMatch, RemediationStep, SourceItem
from app.schemas.ml import MetricTelemetryInput


# ===================== Deep Learning Analysis Schema =====================

class DLLogAnalysisResult(BaseModel):
    """Deep learning sequence evaluation and attention attribution."""

    is_anomaly: bool = Field(..., description="Whether sequence is classified as anomalous by PyTorch model")
    anomaly_probability: float = Field(..., description="Calculated anomaly probability [0.0 - 1.0]")
    predicted_class: int = Field(default=0, description="Predicted class index (0=normal, 1=anomalous)")
    sequence_length: int = Field(default=0, description="Number of evaluated log events in the temporal sequence")
    top_trigger_event: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Top trigger log event isolated by maximum self-attention weight",
    )
    event_tokens: List[str] = Field(default_factory=list, description="Extracted template IDs for each log message")
    attention_weights: List[float] = Field(default_factory=list, description="Self-attention distribution across sequence")
    latency_ms: float = Field(default=0.0, description="Inference latency in milliseconds")


# ===================== Ingest & Trigger Schemas =====================

class TelemetryIngestRequest(BaseModel):
    """Payload to ingest live telemetry, execute ML detection, and orchestrate investigation."""

    service_id: str = Field(..., min_length=1, max_length=100, description="Microservice identifier")
    timestamp: Optional[datetime] = Field(default=None, description="Timestamp of telemetry sample")
    cpu_usage: float = Field(..., ge=0.0, le=100.0, description="CPU utilization percentage")
    memory_usage: float = Field(..., ge=0.0, le=100.0, description="Memory utilization percentage")
    disk_usage: float = Field(default=40.0, ge=0.0, le=100.0, description="Disk utilization percentage")
    network_traffic_kbps: float = Field(default=450.0, ge=0.0, description="Network throughput in KB/s")
    request_count: int = Field(default=100, ge=0, description="Request count in window")
    latency_p95_ms: float = Field(..., ge=0.0, description="95th percentile latency in ms")
    error_rate: float = Field(..., ge=0.0, le=1.0, description="Error rate [0.0 - 1.0]")
    active_connections: int = Field(..., ge=0, description="Concurrent socket connections")

    recent_logs: Optional[List[str]] = Field(
        default=None,
        description="Optional chronological raw log messages for deep learning sequence analysis",
    )
    recent_history: Optional[List[MetricTelemetryInput]] = Field(
        default=None,
        description="Optional recent telemetry points for rolling feature extraction",
    )

    incident_id: Optional[str] = Field(
        default=None,
        description="Optional existing incident ID to associate or update",
    )
    title: Optional[str] = Field(
        default=None,
        description="Optional alert or incident title override",
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional incident description or symptom text",
    )
    anomaly_threshold: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Anomaly score cutoff above which an incident is triggered",
    )
    force_investigation: bool = Field(
        default=False,
        description="If True, runs the full investigation pipeline even if below anomaly threshold",
    )


class ManualInvestigateRequest(BaseModel):
    """Request payload to manually trigger full orchestration on an existing incident."""

    incident_id: str = Field(..., min_length=1, description="Incident ID to investigate")
    time_range: str = Field(default="1h", description="Telemetry lookback window (e.g. '15m', '1h', '24h')")
    recent_logs: Optional[List[str]] = Field(
        default=None,
        description="Optional explicit log sequence to analyze",
    )


# ===================== Complete Investigation Response Schema =====================

class IncidentInvestigationResponse(BaseModel):
    """Exposes the complete incident orchestration state across ML, DL, Agent, and RAG layers."""

    incident_id: str = Field(..., description="Unique incident ID")
    investigation_id: str = Field(..., description="Unique investigation run ID")
    service_id: str = Field(..., description="Affected service ID")
    status: str = Field(..., description="Investigation status (COMPLETED, INSUFFICIENT_EVIDENCE, DEGRADED, FAILED)")

    # 1. Detection Layer
    detected_anomaly: bool = Field(..., description="Whether operational anomaly was detected")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated ML anomaly score [0.0 - 1.0]")
    anomaly_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Contributing signals, algorithm info, and raw deviations",
    )

    # 2. Classification Layer
    predicted_category: str = Field(..., description="Predicted failure domain (database, application, etc.)")
    category_confidence: float = Field(..., ge=0.0, le=1.0, description="Classification model confidence")
    category_probabilities: Optional[Dict[str, float]] = Field(
        default=None,
        description="Full probability distribution across failure domains",
    )

    # 3. Severity Prediction Layer
    predicted_severity: str = Field(..., description="Predicted severity level (P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW)")
    severity_confidence: float = Field(..., ge=0.0, le=1.0, description="Severity model confidence")
    risk_factors: Optional[List[str]] = Field(
        default=None,
        description="Identified risk drivers (e.g., error rate > 5%, latency > 1000ms)",
    )

    # 4. Deep Learning Log Analysis Layer
    dl_log_analysis: Optional[DLLogAnalysisResult] = Field(
        default=None,
        description="PyTorch sequence model prediction and attention trigger attribution",
    )

    # 5. Agent Diagnosis & Synthesis Layer
    suspected_root_cause: str = Field(..., description="Synthesized technical root cause explanation")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Agent grounding and diagnostic confidence score")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Itemized evidentiary artifacts")
    similar_incidents: List[HistoricalIncidentMatch] = Field(
        default_factory=list,
        description="Top matching historical incident postmortems",
    )

    # 6. RAG Grounded Recommendation Layer
    retrieved_sources: List[SourceItem] = Field(
        default_factory=list,
        description="Authoritative runbooks, guides, and documentation cited",
    )
    recommended_remediation: List[RemediationStep] = Field(
        default_factory=list,
        description="Ordered, actionable remediation steps and recovery commands",
    )

    # Observability & Traceability
    timeline: List[str] = Field(default_factory=list, description="Chronological trace of orchestration pipeline stages")
    degraded_components: List[str] = Field(
        default_factory=list,
        description="Components operating in graceful degradation/fallback mode",
    )
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvestigationSummary(BaseModel):
    """Lightweight summary of an incident investigation for list views."""

    investigation_id: str
    incident_id: str
    service_id: str
    status: str
    detected_anomaly: bool
    anomaly_score: float
    predicted_category: str
    predicted_severity: str
    suspected_root_cause: str
    confidence: float
    degraded_components: List[str] = Field(default_factory=list)
    created_at: datetime


class PipelineComponentHealth(BaseModel):
    name: str
    status: str  # READY, DEGRADED, UNAVAILABLE
    version: Optional[str] = None
    details: Optional[str] = None


class PipelineHealthStatusResponse(BaseModel):
    """Health and readiness of all integrated orchestration pipeline layers."""

    pipeline_status: str  # HEALTHY, DEGRADED, CRITICAL
    components: Dict[str, PipelineComponentHealth]
    timestamp: datetime
