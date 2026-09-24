"""FastAPI endpoints for Phase 6 LangGraph Incident Investigation Agent."""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.graph import run_incident_investigation
from app.agent.tools.registry import TOOL_DEFINITIONS, ToolRegistry
from app.db.session import get_db
from app.schemas.agent import InvestigationRequest, InvestigationResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["AI Investigation Agent"])


@router.post(
    "/investigate",
    response_model=InvestigationResult,
    status_code=status.HTTP_200_OK,
    summary="Investigate incident using LangGraph workflow",
)
def investigate_incident(
    request: InvestigationRequest,
    db: Session = Depends(get_db),
) -> InvestigationResult:
    """Execute autonomous incident investigation using the LangGraph state graph.
    
    Workflow:
      Initial Analysis -> Collect Metrics -> [Conditional: Check Deployments] -> Inspect Logs
      -> [Conditional: Validate Signals] -> Search Historical Incidents -> Search Runbooks
      -> Root Cause Analysis -> Confidence Assessment -> [Conditional: Evidence Check]
      -> Recommendation / Insufficient Evidence.
    """
    try:
        logger.info("Starting incident investigation: %s on %s", request.title, request.service)
        return run_incident_investigation(request=request, db=db)
    except Exception as exc:
        logger.error("Incident investigation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation workflow failed: {str(exc)}",
        )


@router.get(
    "/tools",
    summary="List available safe read-only agent tools and boundaries",
)
def list_agent_tools() -> Dict[str, Any]:
    """Retrieve specifications, parameters, and safety boundaries of all available agent tools."""
    return {
        "total_tools": len(TOOL_DEFINITIONS),
        "tools": TOOL_DEFINITIONS,
        "mode": "read_only",
        "safety_guarantee": "No state mutation, destructive commands, or uncontrolled autonomous write operations.",
    }


@router.post(
    "/tools/{tool_name}/execute",
    summary="Safely execute an isolated read-only investigation tool",
)
def execute_tool_endpoint(
    tool_name: str,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Any:
    """Directly invoke a registered read-only tool with parameter validation and boundary enforcement."""
    result = ToolRegistry.execute_tool(tool_name=tool_name, arguments=payload, db=db)
    if isinstance(result, dict) and result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Tool execution failed"),
        )
    return result
