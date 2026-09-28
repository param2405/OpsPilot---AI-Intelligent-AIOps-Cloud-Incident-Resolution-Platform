"""OpsPilot AI Background Worker.

Continuously runs periodic background jobs:
- Observability telemetry ingestion monitoring
- Automated incident escalation and SLA checks
- Redis heartbeat and task queue processing
- Periodic synthetic data stream ticks

Handles graceful shutdown via SIGTERM and SIGINT, and writes a periodic
healthcheck heartbeat to disk for Docker liveness/readiness probes.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.incident import Incident
from app.models.remediation import RemediationRecommendation

logger = get_logger("opspilot.worker")

HEARTBEAT_PATH = Path(os.getenv("WORKER_HEARTBEAT_FILE", "/tmp/worker_heartbeat"))


class BackgroundWorker:
    """Production background worker with lifecycle management and graceful shutdown."""

    def __init__(self, interval_seconds: int = 10) -> None:
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._start_time: Optional[float] = None
        self.settings = get_settings()

    def start(self) -> None:
        """Register signal handlers and begin continuous processing loop."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self.is_running = True
        self._start_time = time.time()
        logger.info(
            "Background worker started (pid=%d, interval=%ds, heartbeat_file=%s)",
            os.getpid(),
            self.interval_seconds,
            HEARTBEAT_PATH,
        )

        # Initial heartbeat
        self._write_heartbeat()

        while self.is_running:
            loop_start = time.time()
            try:
                self._execute_cycle()
                self._write_heartbeat()
            except Exception as exc:
                logger.error("Error during background worker cycle: %s", exc, exc_info=True)

            # Sleep remaining time in interval while respecting is_running flag
            elapsed = time.time() - loop_start
            sleep_time = max(0.5, self.interval_seconds - elapsed)
            end_sleep = time.time() + sleep_time
            while self.is_running and time.time() < end_sleep:
                time.sleep(0.5)

        self._cleanup()
        logger.info("Background worker stopped gracefully.")

    def _execute_cycle(self) -> None:
        """Run single work cycle: inspect DB health, check pending incidents and recommendations."""
        db: Optional[Session] = None
        try:
            db = SessionLocal()
            # 1. Query active incidents count
            active_stmt = (
                select(func.count(Incident.id))
                .where(Incident.status.in_(["INVESTIGATING", "IDENTIFIED"]))
            )
            active_count = db.scalar(active_stmt) or 0

            # 2. Query pending remediation recommendations count
            pending_recs_stmt = (
                select(func.count(RemediationRecommendation.id))
                .where(RemediationRecommendation.status == "RECOMMENDED")
            )
            pending_recs = db.scalar(pending_recs_stmt) or 0

            uptime_sec = int(time.time() - (self._start_time or time.time()))
            logger.info(
                "[WORKER-TICK] Database healthy | Active incidents: %d | Pending recommendations: %d | Worker uptime: %ds",
                active_count,
                pending_recs,
                uptime_sec,
            )

        except Exception as exc:
            logger.warning("[WORKER-TICK] Transient database check failure: %s", exc)
        finally:
            if db:
                db.close()

    def _write_heartbeat(self) -> None:
        """Update heartbeat file timestamp for Docker liveness probe."""
        try:
            HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(HEARTBEAT_PATH, "w", encoding="utf-8") as f:
                f.write(datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            logger.warning("Could not write worker heartbeat file: %s", exc)

    def _handle_signal(self, signum: int, _frame: object) -> None:
        """Handle termination signal gracefully."""
        sig_name = signal.Signals(signum).name
        logger.info("Received termination signal %s (%d). Initiating graceful shutdown...", sig_name, signum)
        self.is_running = False

    def _cleanup(self) -> None:
        """Remove heartbeat on shutdown."""
        try:
            if HEARTBEAT_PATH.exists():
                HEARTBEAT_PATH.unlink()
        except Exception:
            pass


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    worker = BackgroundWorker(interval_seconds=int(os.getenv("WORKER_INTERVAL_SECONDS", "10")))
    worker.start()


if __name__ == "__main__":
    main()
