"""Integration tests for Phase 7 Intelligent Incident Orchestration Pipeline.

Tests:
  1. Full end-to-end 12-step pipeline on anomalous telemetry.
  2. Normal operational telemetry (no anomaly, no alert noise).
  3. Graceful degradation when ML models are unavailable.
  4. Graceful degradation when Deep Learning engine is unavailable.
  5. Graceful handling of agent tool failures.
  6. Transparent handling of insufficient evidence.
  7. API exposure through FastAPI orchestration endpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from collections.abc import Generator
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.incident import Incident
from app.models.investigation import IncidentInvestigation
from app.schemas.orchestration import (
    ManualInvestigateRequest,
    TelemetryIngestRequest,
)
from app.services.orchestration_service import IncidentOrchestrationService


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """In-memory SQLite test database fixture with all domain tables."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.clear()
    session.close()


@pytest.fixture
def client(test_db: Session) -> TestClient:
    return TestClient(app)


# =============================================================================
# 1. Full 12-Step Orchestration on Anomalous Telemetry
# =============================================================================

def test_full_orchestration_anomaly_flow(test_db):
    """Test full 12-step orchestration pipeline triggered by database pool exhaustion anomaly."""
    service = IncidentOrchestrationService()

    payload = TelemetryIngestRequest(
        service_id="order-api",
        cpu_usage=88.5,
        memory_usage=86.2,
        latency_p95_ms=3250.0,
        error_rate=0.185,
        active_connections=185,
        recent_logs=[
            "2026-09-28T09:00:00Z INFO [order-api] Incoming POST /orders",
            "2026-09-28T09:01:00Z WARN [order-api] HikariPool-1 - Connection pool approaching maximum size: active=170, max=200",
            "2026-09-28T09:02:00Z ERROR [order-api] ConnectionTimeoutException: Connection is not available, request timed out after 30000ms",
            "2026-09-28T09:02:30Z FATAL [order-api] HikariPool-1 - Connection is not available, pool exhausted.",
        ],
        title="HikariCP pool saturation on order-api",
        description="Spike in 504 gateway timeouts. Connection pool exhausted.",
        force_investigation=True,
    )

    result = service.process_telemetry(payload=payload, db=test_db)

    # 1. Verification of Required Final Fields
    assert result.incident_id.startswith("INC-")
    assert result.investigation_id.startswith("INV-")
    assert result.service_id == "order-api"
    assert result.status in ("COMPLETED", "DEGRADED")

    # 2. Deterministic ML Findings
    assert result.detected_anomaly is True
    assert result.anomaly_score >= 0.50
    assert result.predicted_category in ("database", "application", "DATABASE")
    assert result.predicted_severity in ("P1_CRITICAL", "P2_HIGH", "CRITICAL", "HIGH")

    # 3. Deep Learning Log Sequence Evaluation
    assert result.dl_log_analysis is not None
    assert result.dl_log_analysis.is_anomaly is True
    assert result.dl_log_analysis.top_trigger_event is not None
    assert "log_message" in result.dl_log_analysis.top_trigger_event

    # 4. Agent Diagnosis & Root Cause Synthesis
    assert result.confidence >= 0.35
    assert len(result.evidence) > 0
    assert "pool" in result.suspected_root_cause.lower() or "connection" in result.suspected_root_cause.lower()

    # 5. RAG Recommendations & Citations
    assert len(result.recommended_remediation) > 0
    assert len(result.retrieved_sources) > 0
    assert len(result.timeline) > 5

    # 6. Database Persistence Verification
    persisted_inv = test_db.get(IncidentInvestigation, result.investigation_id)
    assert persisted_inv is not None
    assert persisted_inv.incident_id == result.incident_id
    assert persisted_inv.detected_anomaly is True
    assert persisted_inv.confidence == result.confidence

    persisted_inc = test_db.get(Incident, result.incident_id)
    assert persisted_inc is not None
    assert persisted_inc.status in ("IDENTIFIED", "INVESTIGATING")
    assert persisted_inc.root_cause != ""


# =============================================================================
# 2. Normal Telemetry Flow (No Anomaly / No Noise)
# =============================================================================

def test_normal_telemetry_no_incident(test_db):
    """Test that normal, baseline telemetry does not create an incident or trigger noise."""
    service = IncidentOrchestrationService()

    payload = TelemetryIngestRequest(
        service_id="payment-service",
        cpu_usage=25.0,
        memory_usage=35.0,
        latency_p95_ms=45.0,
        error_rate=0.001,
        active_connections=15,
        anomaly_threshold=0.60,
        force_investigation=False,
    )

    result = service.process_telemetry(payload=payload, db=test_db)

    assert result.status == "NORMAL"
    assert result.detected_anomaly is False
    assert result.anomaly_score < 0.60
    assert result.incident_id == "NONE"


# =============================================================================
# 3. Graceful Failure: ML Model Unavailable
# =============================================================================

def test_ml_model_unavailable_fallback(test_db):
    """Test that pipeline degrades gracefully to statistical heuristics when ML service fails."""
    mock_ml = MagicMock()
    mock_ml.detect_anomaly.side_effect = RuntimeError("MLflow model registry unavailable")
    mock_ml.classify_incident.side_effect = RuntimeError("Classification model missing")
    mock_ml.predict_severity.side_effect = RuntimeError("Severity model missing")

    service = IncidentOrchestrationService(ml_service=mock_ml)

    payload = TelemetryIngestRequest(
        service_id="inventory-api",
        cpu_usage=95.0,
        memory_usage=88.0,
        latency_p95_ms=2500.0,
        error_rate=0.12,
        active_connections=90,
        recent_logs=["ERROR [inventory-api] Connection timeout to database"],
        force_investigation=True,
    )

    result = service.process_telemetry(payload=payload, db=test_db)

    # Pipeline should complete without exception in degraded mode
    assert result.status == "DEGRADED"
    assert "ml_anomaly_fallback" in result.degraded_components
    assert "ml_classification_fallback" in result.degraded_components
    assert "ml_severity_fallback" in result.degraded_components
    assert result.detected_anomaly is True
    assert result.predicted_severity in ("P1_CRITICAL", "P2_HIGH")
    assert result.predicted_category != "UNKNOWN"


# =============================================================================
# 4. Graceful Failure: DL Log Model Unavailable
# =============================================================================

def test_dl_model_unavailable_fallback(test_db):
    """Test fallback when deep learning checkpoint or inference engine fails."""
    mock_dl = MagicMock()
    mock_dl.predict.side_effect = RuntimeError("PyTorch CUDA out of memory / weights corrupted")

    service = IncidentOrchestrationService(dl_engine=mock_dl)

    payload = TelemetryIngestRequest(
        service_id="checkout-worker",
        cpu_usage=75.0,
        memory_usage=60.0,
        latency_p95_ms=900.0,
        error_rate=0.08,
        active_connections=45,
        recent_logs=[
            "INFO [checkout-worker] Task received",
            "FATAL [checkout-worker] NullPointerException in payment checkout handler",
        ],
        force_investigation=True,
    )

    result = service.process_telemetry(payload=payload, db=test_db)

    assert "dl_log_model_fallback" in result.degraded_components
    assert result.dl_log_analysis is not None
    assert result.dl_log_analysis.top_trigger_event is not None
    assert "NullPointerException" in result.dl_log_analysis.top_trigger_event["log_message"]


# =============================================================================
# 5. Graceful Failure: Agent Tool Failure
# =============================================================================

def test_agent_tool_failure_resilience(test_db):
    """Test that individual diagnostic tool failures do not crash the investigation."""
    service = IncidentOrchestrationService()

    # Simulate get_metrics tool raising an unhandled connection error
    with patch("app.agent.nodes.get_metrics", side_effect=RuntimeError("Prometheus connection refused")):
        payload = TelemetryIngestRequest(
            service_id="shipping-svc",
            cpu_usage=80.0,
            memory_usage=82.0,
            latency_p95_ms=1500.0,
            error_rate=0.09,
            active_connections=70,
            force_investigation=True,
        )

        result = service.process_telemetry(payload=payload, db=test_db)

        # Pipeline should survive and finish
        assert result.incident_id.startswith("INC-")
        assert any("degraded" in e.description.lower() for e in result.evidence)


# =============================================================================
# 6. Insufficient Evidence Handling
# =============================================================================

def test_insufficient_evidence_path(test_db):
    """Test that out-of-domain or ungrounded queries trigger transparent insufficient evidence."""
    service = IncidentOrchestrationService()

    payload = TelemetryIngestRequest(
        service_id="quantum-router",
        cpu_usage=10.0,
        memory_usage=15.0,
        latency_p95_ms=20.0,
        error_rate=0.0,
        active_connections=5,
        title="Unhandled quantum decoherence and teleportation failure",
        description="Quantum key teleportation channel lost coherence.",
        force_investigation=True,
    )

    result = service.process_telemetry(payload=payload, db=test_db)

    assert result.status == "INSUFFICIENT_EVIDENCE"
    assert result.confidence < 0.35
    assert "INSUFFICIENT EVIDENCE" in result.suspected_root_cause


# =============================================================================
# 7. FastAPI Endpoints Integration
# =============================================================================

def test_orchestration_api_endpoints(client: TestClient):
    """Verify HTTP endpoints for telemetry ingestion, querying, and health check."""
    # 1. Pipeline Status
    status_resp = client.get("/api/v1/orchestration/pipeline/status")
    assert status_resp.status_code == 200
    status_body = status_resp.json()
    assert "pipeline_status" in status_body
    assert "components" in status_body
    assert "ml_anomaly" in status_body["components"]
    assert "deep_learning_log_analysis" in status_body["components"]

    # 2. Process Telemetry Endpoint
    payload = {
        "service_id": "auth-service",
        "cpu_usage": 92.0,
        "memory_usage": 85.0,
        "latency_p95_ms": 2800.0,
        "error_rate": 0.15,
        "active_connections": 160,
        "recent_logs": [
            "INFO [auth-service] Processing token validation",
            "ERROR [auth-service] HikariPool-1 - Connection timeout after 30000ms",
        ],
        "force_investigation": True,
    }
    post_resp = client.post("/api/v1/orchestration/process-telemetry", json=payload)
    assert post_resp.status_code == 200
    res_body = post_resp.json()
    assert "investigation_id" in res_body
    assert "incident_id" in res_body
    assert res_body["detected_anomaly"] is True

    inc_id = res_body["incident_id"]

    # 3. Retrieve by ID
    get_resp = client.get(f"/api/v1/orchestration/investigations/{inc_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["incident_id"] == inc_id

    # 4. List Investigations
    list_resp = client.get("/api/v1/orchestration/investigations?limit=10")
    assert list_resp.status_code == 200
    assert isinstance(list_resp.json(), list)
    assert len(list_resp.json()) >= 1
