from datetime import datetime, timezone
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.deployment import Deployment
    from app.models.incident import Incident
    from app.models.log import LogEntry
    from app.models.metric import Metric


class Service(Base):
    """Represents a monitored microservice in the cloud ecosystem."""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    owner_team: Mapped[str] = mapped_column(String(64), default="core-ops", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    metrics: Mapped[List["Metric"]] = relationship(
        "Metric",
        back_populates="service",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    logs: Mapped[List["LogEntry"]] = relationship(
        "LogEntry",
        back_populates="service",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    incidents: Mapped[List["Incident"]] = relationship(
        "Incident",
        back_populates="service",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment",
        back_populates="service",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
