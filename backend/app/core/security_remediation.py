"""Authorization boundaries and security guards for Human-In-The-Loop Remediation."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import Header, HTTPException, status

from app.schemas.remediation import RiskLevel, UserRole

logger = logging.getLogger(__name__)


class RemediationAuthorizationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def verify_approval_authorization(user_role: UserRole, risk_level: str) -> None:
    """Enforce authorization boundaries for human approval of remediation actions.
    
    SECURITY RULES:
    1. AI_AGENT is strictly forbidden from approving any remediation actions!
    2. VIEWER has read-only access and cannot approve or reject.
    3. OPERATOR can only approve LOW risk actions.
    4. SRE_LEAD and PLATFORM_ADMIN can approve LOW, MEDIUM, and HIGH risk actions.
    """
    if user_role == UserRole.AI_AGENT:
        logger.error("Security alert: Autonomous AI agent attempted to approve its own remediation recommendation!")
        raise RemediationAuthorizationError(
            "Security boundary violation: AI agents are strictly forbidden from approving remediation actions. Human approval is required."
        )

    if user_role == UserRole.VIEWER:
        raise RemediationAuthorizationError(
            "Insufficient permissions: Users with 'VIEWER' role cannot approve remediation actions."
        )

    if user_role == UserRole.OPERATOR:
        if risk_level.upper() in (RiskLevel.HIGH.value, RiskLevel.MEDIUM.value):
            raise RemediationAuthorizationError(
                f"Insufficient permissions: 'OPERATOR' role can only approve LOW risk actions. Current action risk is '{risk_level}'. Requires SRE_LEAD or PLATFORM_ADMIN."
            )
        return

    if user_role in (UserRole.SRE_LEAD, UserRole.PLATFORM_ADMIN):
        # Permitted for all risk levels
        return

    # Fallback for unknown role
    raise RemediationAuthorizationError(f"Unauthorized role: '{user_role}'")


def get_authenticated_user_context(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id", description="Authenticated user ID or email"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role", description="Authenticated RBAC role"),
) -> tuple[str, UserRole]:
    """Extract authenticated operator context from headers with safe defaults for development."""
    user_id = x_user_id or "sre-lead@opspilot.io"
    role_str = (x_user_role or "SRE_LEAD").upper()
    try:
        user_role = UserRole(role_str)
    except ValueError:
        user_role = UserRole.VIEWER

    return user_id, user_role
