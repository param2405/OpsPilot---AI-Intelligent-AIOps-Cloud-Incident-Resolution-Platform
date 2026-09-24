"""Unified registry and dispatcher for safe read-only SRE investigation tools."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from app.agent.tools.deployments_tool import get_recent_deployments
from app.agent.tools.historical_tool import search_historical_incidents
from app.agent.tools.logs_tool import search_logs
from app.agent.tools.metrics_tool import get_metrics
from app.agent.tools.runbooks_tool import search_runbooks
from app.agent.tools.statistics_tool import calculate_statistics

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "name": "get_metrics",
        "description": "Collects telemetry metrics (CPU, memory, error rate, p95 latency, connections) for a service over a time range and flags baseline anomalies.",
        "parameters": {
            "service": "str (required)",
            "time_range": "str (optional, default '1h', max '7d')",
        },
        "safety_boundaries": "Strictly read-only; service name validated; time range capped at 7 days.",
    },
    {
        "name": "search_logs",
        "description": "Searches application error logs and warning traces matching a query keyword or error signature for a given service.",
        "parameters": {
            "service": "str (required)",
            "query": "str (optional)",
            "time_range": "str (optional, default '1h')",
            "limit": "int (optional, default 20, max 50)",
        },
        "safety_boundaries": "Strictly read-only; output capped at 50 log records; query regex sanitized.",
    },
    {
        "name": "search_historical_incidents",
        "description": "Searches past postmortems and resolved incident reports for matching symptoms, root causes, and proven resolutions.",
        "parameters": {
            "query": "str (required)",
            "limit": "int (optional, default 3, max 10)",
        },
        "safety_boundaries": "Strictly read-only; hybrid semantic vector search; top-K capped at 10.",
    },
    {
        "name": "search_runbooks",
        "description": "Retrieves operational runbooks and database guides with diagnostic CLI queries and step-by-step remediation procedures.",
        "parameters": {
            "query": "str (required)",
            "service": "str (optional)",
            "limit": "int (optional, default 3, max 10)",
        },
        "safety_boundaries": "Strictly read-only; hybrid search with contextual reranking; top-K capped at 10.",
    },
    {
        "name": "get_recent_deployments",
        "description": "Checks recent deployment releases, Argo Rollout canary progression, and rollout failure statuses for a service.",
        "parameters": {
            "service": "str (required)",
            "limit": "int (optional, default 5, max 10)",
        },
        "safety_boundaries": "Strictly read-only; limited to recent releases.",
    },
    {
        "name": "calculate_statistics",
        "description": "Computes statistical summary (mean, std dev, min, max, median, p95, p99, anomaly detection) on numerical telemetry data.",
        "parameters": {
            "data": "List[float] (required, max 10,000 points)",
            "metric_name": "str (optional)",
        },
        "safety_boundaries": "Pure mathematical calculation; memory and size bounded.",
    },
]


class ToolRegistry:
    """Central registry and execution coordinator for read-only agent tools."""

    @staticmethod
    def get_tool_specs() -> List[Dict[str, Any]]:
        return TOOL_DEFINITIONS

    @staticmethod
    def execute_tool(
        tool_name: str,
        arguments: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> Any:
        """Safely dispatch and execute a registered tool by name with exception handling."""
        logger.info("ToolRegistry dispatching tool '%s' with args %s", tool_name, arguments)
        try:
            if tool_name == "get_metrics":
                return get_metrics(
                    service=arguments.get("service", "unknown"),
                    time_range=arguments.get("time_range", "1h"),
                    db=db,
                )
            elif tool_name == "search_logs":
                return search_logs(
                    service=arguments.get("service", "unknown"),
                    query=arguments.get("query", ""),
                    time_range=arguments.get("time_range", "1h"),
                    limit=arguments.get("limit", 20),
                    db=db,
                )
            elif tool_name == "search_historical_incidents":
                return search_historical_incidents(
                    query=arguments.get("query", ""),
                    limit=arguments.get("limit", 3),
                    db=db,
                )
            elif tool_name == "search_runbooks":
                return search_runbooks(
                    query=arguments.get("query", ""),
                    service=arguments.get("service"),
                    limit=arguments.get("limit", 3),
                    db=db,
                )
            elif tool_name == "get_recent_deployments":
                return get_recent_deployments(
                    service=arguments.get("service", "unknown"),
                    limit=arguments.get("limit", 5),
                    db=db,
                )
            elif tool_name == "calculate_statistics":
                return calculate_statistics(
                    data=arguments.get("data", []),
                    metric_name=arguments.get("metric_name", "metric"),
                )
            else:
                raise ValueError(f"Unknown tool requested: '{tool_name}'")
        except Exception as exc:
            logger.error("Error executing tool '%s': %s", tool_name, exc, exc_info=True)
            return {
                "status": "error",
                "tool": tool_name,
                "error": str(exc),
            }
