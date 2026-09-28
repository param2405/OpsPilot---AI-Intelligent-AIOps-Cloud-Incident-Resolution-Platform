"""Domain model for Incident Investigation capturing the end-to-end orchestration output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.incident import Incident


class IncidentInvestigation(Base):
    """Complete diagnostic investigation record integrating ML, DL, Agent, and RAG layers."""

    __tablename__ = "incident_investigations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "INV-20260928-123456-ABC"
    incident_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default="COMPLETED",
        nullable=False,
        index=True,
    )  # COMPLETED, INSUFFICIENT_EVIDENCE, DEGRADED, FAILED

    # 1. Deterministic ML Anomaly Detection Layer
    detected_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    anomaly_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 2. Deterministic ML Failure Classification Layer
    predicted_category: Mapped[str] = mapped_column(String(64), default="UNKNOWN", nullable=False, index=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    category_probabilities: Mapped[Optional[Dict[str, float]]] = mapped_column(JSON, nullable=True)

    # 3. Deterministic ML Severity Prediction Layer
    predicted_severity: Mapped[str] = mapped_column(String(32), default="P3_MEDIUM", nullable=False, index=True)
    severity_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk_factors: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    # 4. Deep Learning Log Sequence Analysis Layer
    dl_log_analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 5. Agent Diagnostic & Causal Synthesis Layer
    suspected_root_cause: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    similar_incidents: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    # 6. RAG Grounded Retrieval & Recommendation Layer
    retrieved_sources: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    recommended_remediation: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    # Observability, Degraded Components, and Execution Trace
    timeline: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    degraded_components: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

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

    incident: Mapped["Incident"] = relationship("Incident", back_populates="investigations")
