from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.deployment import Deployment
    from app.models.service import Service


class Incident(Base):
    """Historical or active incident record capturing symptoms, root cause, and remediation."""

    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "INC-2026-001"
    service_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # P1_CRITICAL, P2_HIGH, P3_MEDIUM, P4_LOW
    symptoms: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="RESOLVED", nullable=False, index=True)  # INVESTIGATING, IDENTIFIED, MITIGATED, RESOLVED
    incident_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    related_deployment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("deployments.id", ondelete="SET NULL"),
        nullable=True,
    )

    service: Mapped["Service"] = relationship("Service", back_populates="incidents")
    related_deployment: Mapped[Optional["Deployment"]] = relationship(
        "Deployment",
        back_populates="incidents",
    )
