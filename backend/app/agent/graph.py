"""LangGraph Incident Investigation Workflow assembling state, nodes, conditional edges, and compilation."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import (
    check_deployments_node,
    collect_metrics_node,
    confidence_assessment_node,
    initial_analysis_node,
    inspect_logs_node,
    insufficient_evidence_node,
    recommendation_node,
    root_cause_analysis_node,
    search_historical_incidents_node,
    search_runbooks_node,
)
from app.agent.routing import (
    route_after_confidence,
    route_after_logs,
    route_after_metrics,
)
from app.agent.state import InvestigationState
from app.schemas.agent import (
    EvidenceItem,
    HistoricalIncidentMatch,
    InvestigationRequest,
    InvestigationResult,
    RemediationStep,
    SourceItem,
)

logger = logging.getLogger(__name__)


def build_incident_investigation_graph() -> StateGraph:
    """Construct the explicit, safe, read-only incident investigation state graph.
    
    Graph Topology:
      START
        ↓
      initial_analysis
        ↓
      collect_metrics
        ↓ (Conditional Router 1: route_after_metrics)
        ├──> check_deployments ──> inspect_logs
        └──> inspect_logs
               ↓ (Conditional Router 2: route_after_logs)
               ├──> insufficient_evidence ──> END
               └──> search_historical_incidents
                      ↓
                    search_runbooks
                      ↓
                    root_cause_analysis
                      ↓
                    confidence_assessment
                      ↓ (Conditional Router 3: route_after_confidence)
                      ├──> insufficient_evidence ──> END
                      └──> recommendation ──> END
    """
    workflow = StateGraph(InvestigationState)

    # 1. Register Execution Nodes
    workflow.add_node("initial_analysis", initial_analysis_node)
    workflow.add_node("collect_metrics", collect_metrics_node)
    workflow.add_node("check_deployments", check_deployments_node)
    workflow.add_node("inspect_logs", inspect_logs_node)
    workflow.add_node("search_historical_incidents", search_historical_incidents_node)
    workflow.add_node("search_runbooks", search_runbooks_node)
    workflow.add_node("root_cause_analysis", root_cause_analysis_node)
    workflow.add_node("confidence_assessment", confidence_assessment_node)
    workflow.add_node("recommendation", recommendation_node)
    workflow.add_node("insufficient_evidence", insufficient_evidence_node)

    # 2. Add Deterministic & Conditional Edges
    workflow.add_edge(START, "initial_analysis")
    workflow.add_edge("initial_analysis", "collect_metrics")

    # Conditional Branch 1: Check deployments only if correlated/needed
    workflow.add_conditional_edges(
        "collect_metrics",
        route_after_metrics,
        {
            "check_deployments": "check_deployments",
            "inspect_logs": "inspect_logs",
        },
    )
    workflow.add_edge("check_deployments", "inspect_logs")

    # Conditional Branch 2: Check if initial observability signals exist
    workflow.add_conditional_edges(
        "inspect_logs",
        route_after_logs,
        {
            "search_historical_incidents": "search_historical_incidents",
            "insufficient_evidence": "insufficient_evidence",
        },
    )

    # Grounded Knowledge Retrieval & Synthesis
    workflow.add_edge("search_historical_incidents", "search_runbooks")
    workflow.add_edge("search_runbooks", "root_cause_analysis")
    workflow.add_edge("root_cause_analysis", "confidence_assessment")

    # Conditional Branch 3: Verify confidence and evidence sufficiency
    workflow.add_conditional_edges(
        "confidence_assessment",
        route_after_confidence,
        {
            "recommendation": "recommendation",
            "insufficient_evidence": "insufficient_evidence",
        },
    )

    workflow.add_edge("recommendation", END)
    workflow.add_edge("insufficient_evidence", END)

    return workflow


# Compiled singleton graph
investigation_graph = build_incident_investigation_graph().compile()


def run_incident_investigation(
    request: InvestigationRequest,
    db: Optional[Session] = None,
) -> InvestigationResult:
    """Execute the compiled LangGraph incident investigation workflow and format structured result."""
    initial_state: InvestigationState = {
        "incident_id": request.incident_id or f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "service": request.service,
        "title": request.title,
        "description": request.description,
        "severity": request.severity,
        "time_range": request.time_range,
    }

    logger.info("Executing LangGraph investigation for incident %s on service %s", initial_state["incident_id"], request.service)
    final_state = investigation_graph.invoke(initial_state)

    # Format into typed Pydantic output
    evidence_models = [EvidenceItem(**e) for e in final_state.get("evidence", [])]
    historical_models = [HistoricalIncidentMatch(**h) for h in final_state.get("historical_incidents", [])]
    remediation_models = [RemediationStep(**r) for r in final_state.get("recommended_remediation", [])]
    source_models = [SourceItem(**s) for s in final_state.get("sources", [])]

    summary = (
        f"Investigation for '{request.title}' affecting service '{request.service}' ({request.severity}). "
        f"Domain identified: {final_state.get('suspected_domain', 'general')}. "
        f"{len(evidence_models)} evidentiary artifacts collected across metrics, logs, deployments, and runbooks."
    )

    return InvestigationResult(
        incident_id=final_state.get("incident_id", "INC"),
        service=request.service,
        incident_summary=summary,
        suspected_root_cause=final_state.get("suspected_root_cause", "Analysis incomplete"),
        evidence=evidence_models,
        confidence=final_state.get("confidence_score", 0.0),
        has_sufficient_evidence=final_state.get("has_sufficient_evidence", True),
        insufficient_evidence_reason=final_state.get("insufficient_evidence_reason"),
        relevant_historical_incidents=historical_models,
        recommended_remediation=remediation_models,
        sources=source_models,
        investigation_timeline=final_state.get("investigation_timeline", []),
        completed_at=datetime.now(timezone.utc),
    )
