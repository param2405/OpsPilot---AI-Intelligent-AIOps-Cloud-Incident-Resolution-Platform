from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.incident import Incident
    from app.models.service import Service


class Deployment(Base):
    """Deployment event records version changes, rollout timestamps, and release statuses."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(32), default="production", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", nullable=False)  # SUCCESS, FAILED, ROLLED_BACK
    changelog: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    service: Mapped["Service"] = relationship("Service", back_populates="deployments")
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident",
        back_populates="related_deployment",
    )
