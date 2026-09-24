"""Data collection and ground-truth labeling module for OpsPilot AI.

Extracts telemetry time-series and incident records from the database,
and assigns ground-truth anomaly labels based on recorded incident operational windows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.incident import Incident
from app.models.log import LogEntry
from app.models.metric import Metric
from app.models.service import Service


class ObservabilityDataCollector:
    """Collects telemetry metrics and labels ground-truth anomaly periods."""

    def __init__(self, db: Optional[Session] = None) -> None:
        self._db = db

    def _get_db(self) -> Session:
        return self._db if self._db is not None else SessionLocal()

    @staticmethod
    def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def load_telemetry_with_ground_truth(self) -> pd.DataFrame:
        """Load telemetry metrics from DB and compute ground-truth anomaly labels.
        
        Returns:
            DataFrame with telemetry metrics plus 'is_anomaly' (int: 0 or 1).
        """
        db = self._get_db()
        should_close = self._db is None
        try:
            # 1. Fetch all metrics
            metric_stmt = select(Metric).order_by(Metric.timestamp.asc())
            metric_records = db.scalars(metric_stmt).all()

            if not metric_records:
                raise ValueError("No telemetry metrics found in database. Please run seed script first.")

            metrics_data = [
                {
                    "id": m.id,
                    "service_id": m.service_id,
                    "timestamp": self._to_utc(m.timestamp),
                    "cpu_usage": m.cpu_usage,
                    "memory_usage": m.memory_usage,
                    "disk_usage": m.disk_usage,
                    "network_traffic_kbps": m.network_traffic_kbps,
                    "request_count": m.request_count,
                    "latency_p95_ms": m.latency_p95_ms,
                    "error_rate": m.error_rate,
                    "active_connections": m.active_connections,
                }
                for m in metric_records
            ]
            df = pd.DataFrame(metrics_data)

            # 2. Fetch incidents to establish ground-truth anomaly time intervals
            incident_stmt = select(Incident)
            incident_records = db.scalars(incident_stmt).all()

            # Active intervals per service
            incident_intervals = []
            for inc in incident_records:
                start = self._to_utc(inc.started_at)
                end = self._to_utc(inc.resolved_at) or start
                incident_intervals.append(
                    {
                        "service_id": inc.service_id,
                        "incident_type": inc.incident_type,
                        "start": start,
                        "end": end,
                    }
                )

            # 3. Label ground truth: 1 if within incident window, 0 otherwise
            is_anomaly_flags = []
            for _, row in df.iterrows():
                svc = row["service_id"]
                ts = row["timestamp"]
                anom = 0
                for inc in incident_intervals:
                    if inc["service_id"] == svc and inc["start"] <= ts <= inc["end"]:
                        anom = 1
                        break
                    # Cascading impact on API gateway
                    if svc == "api-gateway" and inc["incident_type"] == "API_LATENCY_SPIKE" and inc["start"] <= ts <= inc["end"]:
                        anom = 1
                        break
                is_anomaly_flags.append(anom)

            df["is_anomaly"] = is_anomaly_flags
            return df
        finally:
            if should_close:
                db.close()

    def load_logs_with_ground_truth(self) -> pd.DataFrame:
        """Load operational logs from DB and label ground-truth anomaly events.
        
        Returns:
            DataFrame with 'id', 'service_id', 'timestamp', 'log_level', 'message',
            'trace_id', 'incident_id', and 'is_anomaly' (int: 0 or 1).
        """
        db = self._get_db()
        should_close = self._db is None
        try:
            log_stmt = select(LogEntry).order_by(LogEntry.timestamp.asc())
            log_records = db.scalars(log_stmt).all()

            if not log_records:
                raise ValueError("No log records found in database. Please run seed script first.")

            logs_data = [
                {
                    "id": log.id,
                    "service_id": log.service_id,
                    "timestamp": self._to_utc(log.timestamp),
                    "log_level": log.log_level,
                    "message": log.message,
                    "trace_id": log.trace_id,
                }
                for log in log_records
            ]
            df = pd.DataFrame(logs_data)

            # Query incidents to establish ground-truth incident intervals
            incident_stmt = select(Incident)
            incident_records = db.scalars(incident_stmt).all()

            incident_intervals = []
            for inc in incident_records:
                start = self._to_utc(inc.started_at)
                end = self._to_utc(inc.resolved_at) or start
                incident_intervals.append(
                    {
                        "incident_id": inc.id,
                        "service_id": inc.service_id,
                        "incident_type": inc.incident_type,
                        "start": start,
                        "end": end,
                    }
                )

            is_anomaly_flags = []
            incident_ids = []
            for _, row in df.iterrows():
                svc = row["service_id"]
                ts = row["timestamp"]
                lvl = row["log_level"]
                anom = 0
                inc_id = None

                for inc in incident_intervals:
                    if inc["service_id"] == svc and inc["start"] <= ts <= inc["end"]:
                        anom = 1
                        inc_id = inc["incident_id"]
                        break
                    if svc == "api-gateway" and inc["incident_type"] == "API_LATENCY_SPIKE" and inc["start"] <= ts <= inc["end"]:
                        anom = 1
                        inc_id = inc["incident_id"]
                        break

                # Also flag severe error logs as anomalous
                if lvl in ("ERROR", "FATAL"):
                    anom = 1

                is_anomaly_flags.append(anom)
                incident_ids.append(inc_id)

            df["is_anomaly"] = is_anomaly_flags
            df["incident_id"] = incident_ids
            return df
        finally:
            if should_close:
                db.close()

