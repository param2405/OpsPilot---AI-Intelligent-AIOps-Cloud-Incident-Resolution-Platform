"""Domain models for Phase 9: Human-In-The-Loop Remediation & Security Audit Logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.investigation import IncidentInvestigation


class RemediationRecommendation(Base):
    """Structured remediation action recommended by AI, awaiting human approval."""

    __tablename__ = "remediation_recommendations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "REC-20260928-123456-ABC"
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    investigation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("incident_investigations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Strictly allowlisted action type (restart_service, scale_service, rollback_deployment, etc.)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_service: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", nullable=False)  # LOW, MEDIUM, HIGH

    # Lifecycle Status: RECOMMENDED, APPROVED, EXECUTING, SUCCESS, FAILED, REJECTED
    status: Mapped[str] = mapped_column(
        String(32),
        default="RECOMMENDED",
        nullable=False,
        index=True,
    )

    command_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    runbook_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    incident: Mapped["Incident"] = relationship("Incident", back_populates="remediations")
    investigation: Mapped[Optional["IncidentInvestigation"]] = relationship("IncidentInvestigation")
    audit_logs: Mapped[List["RemediationAuditLog"]] = relationship(
        "RemediationAuditLog",
        back_populates="recommendation",
        cascade="all, delete-orphan",
        order_by="desc(RemediationAuditLog.timestamp)",
    )


class RemediationAuditLog(Base):
    """Immutable audit log for all human-in-the-loop remediation approvals, executions, and rejections."""

    __tablename__ = "remediation_audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "AUD-20260928-123456-ABC"
    recommendation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("remediation_recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    requested_action: Mapped[str] = mapped_column(String(64), nullable=False)
    action_parameters: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    simulation_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Human Approval Details: approved_by, user_role, approved_at, rejection_reason
    user_approval: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Executor Result Details: output, execution_duration_ms, simulated, logs, validation_passed
    executor_result: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Outcome Status: SUCCESS, FAILED, REJECTED
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    recommendation: Mapped["RemediationRecommendation"] = relationship(
        "RemediationRecommendation", back_populates="audit_logs"
    )
