"""Conditional routing functions for LangGraph incident investigation agent."""

from __future__ import annotations

import logging
from typing import Literal

from app.agent.state import InvestigationState

logger = logging.getLogger(__name__)


def route_after_metrics(state: InvestigationState) -> Literal["check_deployments", "inspect_logs"]:
    """Conditional Router 1: Determine whether deployment inspection is warranted based on metrics.
    
    Rule:
      If error rate spiked abruptly (>3.0%) or title/description mentions release/deploy,
      route to deployment inspection. Otherwise, skip directly to log inspection to avoid blind tool calls.
    """
    check_deploy = state.get("check_deployment_needed", False)
    title_lower = state.get("title", "").lower()
    desc_lower = state.get("description", "").lower()

    if check_deploy or "deploy" in title_lower or "release" in title_lower or "deploy" in desc_lower:
        logger.info("Routing -> check_deployments (deployment correlation suspected)")
        return "check_deployments"

    logger.info("Routing -> inspect_logs (skipping deployment check; no release indicators)")
    return "inspect_logs"


def route_after_logs(state: InvestigationState) -> Literal["search_historical_incidents", "insufficient_evidence"]:
    """Conditional Router 2: Verify whether adequate initial observability evidence exists to proceed.
    
    Rule:
      If neither metric anomalies nor relevant error logs were discovered, halt and route to insufficient_evidence.
      Otherwise, continue to historical incident search.
    """
    metric_anomalies = state.get("metric_anomalies", [])
    logs = state.get("logs_data", [])

    if not metric_anomalies and not logs:
        logger.warning("Routing -> insufficient_evidence (zero metric anomalies and zero error logs found)")
        return "insufficient_evidence"

    logger.info("Routing -> search_historical_incidents (sufficient telemetry signals present)")
    return "search_historical_incidents"


def route_after_confidence(state: InvestigationState) -> Literal["recommendation", "insufficient_evidence"]:
    """Conditional Router 3: Gate recommendation based on evidence sufficiency and confidence score.
    
    Rule:
      If confidence score >= 0.35 and has_sufficient_evidence is True, proceed to actionable recommendation.
      Otherwise, route to transparent insufficient evidence disclosure.
    """
    has_evidence = state.get("has_sufficient_evidence", True)
    confidence = state.get("confidence_score", 0.0)

    if has_evidence and confidence >= 0.35:
        logger.info("Routing -> recommendation (confidence=%.2f >= 0.35)", confidence)
        return "recommendation"

    logger.warning("Routing -> insufficient_evidence (confidence=%.2f < 0.35 or insufficient evidence flagged)", confidence)
    return "insufficient_evidence"
