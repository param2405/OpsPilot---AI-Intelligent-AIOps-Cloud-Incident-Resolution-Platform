"""TypedDict state definition for LangGraph incident investigation workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class InvestigationState(TypedDict, total=False):
    """Execution state passed between nodes in the LangGraph incident investigation graph."""

    # Incident Context
    incident_id: str
    service: str
    title: str
    description: str
    severity: str
    time_range: str

    # Diagnostic Hypotheses & Domain Classification
    suspected_domain: str  # database, deployment, jvm_memory, messaging, general
    has_database_symptoms: bool
    has_recent_deployments: bool
    check_deployment_needed: bool

    # Collected Observability Evidence
    metrics_data: Optional[Dict[str, float]]
    metric_anomalies: List[str]
    logs_data: List[Dict[str, Any]]
    log_signatures: List[str]
    deployments: List[Dict[str, Any]]
    deployment_correlated: bool

    # Grounded Knowledge Artifacts
    historical_incidents: List[Dict[str, Any]]
    runbooks: List[Dict[str, Any]]

    # Diagnostic Synthesis & Evaluation
    suspected_root_cause: str
    confidence_score: float
    evidence: List[Dict[str, Any]]
    recommended_remediation: List[Dict[str, Any]]
    sources: List[Dict[str, Any]]

    # Guardrails & Rejection Handling
    has_sufficient_evidence: bool
    insufficient_evidence_reason: Optional[str]

    # Execution Observability & Timeline
    investigation_timeline: List[str]
    final_report: Optional[Dict[str, Any]]
