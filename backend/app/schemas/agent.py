"""Pydantic schemas for Phase 6 LangGraph Incident Investigation Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- Tool Input & Output Schemas ---

class GetMetricsInput(BaseModel):
    service: str = Field(..., min_length=1, max_length=100, description="Name of the service to inspect")
    time_range: str = Field(default="1h", description="Time window for metrics (e.g. '15m', '1h', '6h', '24h')")


class MetricTrend(BaseModel):
    metric_name: str
    current_value: float
    baseline_value: float
    deviation_percent: float
    is_anomaly: bool
    unit: str


class GetMetricsOutput(BaseModel):
    service: str
    time_range: str
    timestamp: datetime
    metrics: Dict[str, float]
    trends: List[MetricTrend]
    anomalies_detected: List[str]
    status: str = "success"


class SearchLogsInput(BaseModel):
    service: str = Field(..., min_length=1, max_length=100, description="Service name")
    query: str = Field(default="", max_length=200, description="Search term, keyword, or error code")
    time_range: str = Field(default="1h", description="Time range for log search")
    limit: int = Field(default=20, ge=1, le=50, description="Maximum number of log entries to retrieve")


class LogMatch(BaseModel):
    id: str
    timestamp: datetime
    level: str
    service: str
    message: str
    event_id: Optional[str] = None


class SearchLogsOutput(BaseModel):
    service: str
    query: str
    total_found: int
    logs: List[LogMatch]
    error_frequency: Dict[str, int]
    status: str = "success"


class SearchHistoricalIncidentsInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=300, description="Incident symptom, error description, or root cause query")
    limit: int = Field(default=3, ge=1, le=10, description="Max historical matches to return")


class HistoricalIncidentMatch(BaseModel):
    incident_id: str
    title: str
    severity: str
    service: str
    root_cause_summary: str
    resolution: str
    similarity_score: float
    occurred_at: Optional[datetime] = None


class SearchHistoricalIncidentsOutput(BaseModel):
    query: str
    total_matches: int
    incidents: List[HistoricalIncidentMatch]
    status: str = "success"


class SearchRunbooksInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=300, description="Symptom, error code, or procedural query")
    service: Optional[str] = Field(default=None, description="Optional service scope filter")
    limit: int = Field(default=3, ge=1, le=10, description="Max runbook sections to return")


class RunbookMatch(BaseModel):
    document_id: str
    title: str
    section: str
    service: str
    relevance_score: float
    diagnostic_commands: List[str]
    remediation_steps: List[str]
    snippet: str


class SearchRunbooksOutput(BaseModel):
    query: str
    total_matches: int
    runbooks: List[RunbookMatch]
    status: str = "success"


class GetRecentDeploymentsInput(BaseModel):
    service: str = Field(..., min_length=1, max_length=100, description="Service name")
    limit: int = Field(default=5, ge=1, le=10, description="Max deployments to return")


class DeploymentRecord(BaseModel):
    deployment_id: str
    service: str
    revision: str
    image_tag: str
    status: str
    deployed_at: datetime
    error_rate_during_canary: Optional[float] = None
    is_recent: bool


class GetRecentDeploymentsOutput(BaseModel):
    service: str
    deployments: List[DeploymentRecord]
    has_recent_deployments: bool
    status: str = "success"


class CalculateStatisticsInput(BaseModel):
    data: List[float] = Field(..., min_length=1, max_length=10000, description="List of numerical values")
    metric_name: Optional[str] = Field(default="metric", description="Name of the metric")


class CalculateStatisticsOutput(BaseModel):
    metric_name: str
    count: int
    mean: float
    std_dev: float
    min: float
    max: float
    median: float
    p95: float
    p99: float
    anomaly_detected: bool
    status: str = "success"


# --- Final Investigation Structured Output Schemas ---

class EvidenceItem(BaseModel):
    category: str = Field(..., description="Evidence type: metric, log, deployment, historical, runbook")
    source: str = Field(..., description="Tool or document providing the evidence")
    description: str = Field(..., description="Detailed factual finding")
    severity_contribution: str = Field(default="medium", description="critical, high, medium, low")


class RemediationStep(BaseModel):
    step_number: int
    action: str
    command_or_config: Optional[str] = None
    risk_level: str = Field(default="low", description="low, medium, high")
    source_reference: Optional[str] = None


class SourceItem(BaseModel):
    title: str
    source_type: str
    reference_id: str
    section: Optional[str] = None


class InvestigationRequest(BaseModel):
    """Input payload to trigger an incident investigation."""

    incident_id: Optional[str] = Field(default=None, description="Existing incident ID in the system")
    service: str = Field(..., min_length=1, description="Target service affected")
    title: str = Field(..., min_length=3, description="Incident title or alert name")
    description: str = Field(default="", description="Detailed incident description or symptom text")
    severity: str = Field(default="P2", description="Incident severity (P1, P2, P3, P4)")
    time_range: str = Field(default="1h", description="Investigation time range")


class InvestigationResult(BaseModel):
    """Final, typed structured output of the LangGraph investigation agent."""

    incident_id: str
    service: str
    incident_summary: str
    suspected_root_cause: str
    evidence: List[EvidenceItem]
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score [0.0 - 1.0]")
    has_sufficient_evidence: bool
    insufficient_evidence_reason: Optional[str] = None
    relevant_historical_incidents: List[HistoricalIncidentMatch]
    recommended_remediation: List[RemediationStep]
    sources: List[SourceItem]
    investigation_timeline: List[str]
    completed_at: datetime
