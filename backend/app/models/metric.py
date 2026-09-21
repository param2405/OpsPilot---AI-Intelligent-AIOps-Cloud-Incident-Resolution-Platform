from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.service import Service


class Metric(Base):
    """Time-series telemetry metric record captured from an operational service."""

    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False)  # % usage [0.0 - 100.0]
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False)  # % usage [0.0 - 100.0]
    disk_usage: Mapped[float] = mapped_column(Float, nullable=False)  # % usage [0.0 - 100.0]
    network_traffic_kbps: Mapped[float] = mapped_column(Float, nullable=False)  # Throughput in KB/s
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)  # Sample window count
    latency_p95_ms: Mapped[float] = mapped_column(Float, nullable=False)  # 95th percentile latency in ms
    error_rate: Mapped[float] = mapped_column(Float, nullable=False)  # Failed request ratio [0.0 - 1.0]
    active_connections: Mapped[int] = mapped_column(Integer, nullable=False)  # Concurrent active sockets/pools

    service: Mapped["Service"] = relationship("Service", back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_service_id_timestamp", "service_id", "timestamp"),
    )
