"""Unit and integration tests for LangGraph incident investigation workflow."""

from __future__ import annotations

import pytest
from app.agent.graph import build_incident_investigation_graph, run_incident_investigation
from app.schemas.agent import InvestigationRequest, InvestigationResult


def test_graph_compilation():
    workflow = build_incident_investigation_graph()
    app = workflow.compile()
    assert app is not None
    # Check that required nodes are present
    assert "initial_analysis" in app.nodes
    assert "collect_metrics" in app.nodes
    assert "check_deployments" in app.nodes
    assert "inspect_logs" in app.nodes
    assert "search_historical_incidents" in app.nodes
    assert "search_runbooks" in app.nodes
    assert "root_cause_analysis" in app.nodes
    assert "confidence_assessment" in app.nodes
    assert "recommendation" in app.nodes
    assert "insufficient_evidence" in app.nodes


def test_investigation_grounded_success():
    req = InvestigationRequest(
        service="order-service",
        title="PostgreSQL connection pool exhausted on order-service",
        description="HikariPool acquisition timeout after 30000ms. Active connections saturated at 192/200.",
        severity="P1",
        time_range="1h",
    )
    result = run_incident_investigation(req)
    assert isinstance(result, InvestigationResult)
    assert result.service == "order-service"
    assert result.has_sufficient_evidence is True
    assert result.confidence >= 0.50
    assert len(result.evidence) >= 3
    assert len(result.sources) >= 2
    assert len(result.recommended_remediation) >= 1
    assert "pool" in result.suspected_root_cause.lower() or "connection" in result.suspected_root_cause.lower()
    assert len(result.investigation_timeline) >= 5


def test_investigation_insufficient_evidence():
    req = InvestigationRequest(
        service="quantum-node-01",
        title="Quantum teleportation qubit entanglement decoherence",
        description="Qubits experienced spontaneous phase collapse.",
        severity="P1",
    )
    result = run_incident_investigation(req)
    assert isinstance(result, InvestigationResult)
    assert result.has_sufficient_evidence is False
    assert result.confidence < 0.35
    assert "insufficient evidence" in result.suspected_root_cause.lower()
    assert result.insufficient_evidence_reason is not None


def test_conditional_routing_deployment_check():
    # If title mentions release, check_deployments should be executed
    req = InvestigationRequest(
        service="order-service",
        title="Canary release v2.4.1 error rate spike",
        description="Post deployment HTTP 5xx errors jumped above threshold.",
        severity="P2",
    )
    result = run_incident_investigation(req)
    timeline_str = " ".join(result.investigation_timeline)
    assert "Deployment check completed" in timeline_str
