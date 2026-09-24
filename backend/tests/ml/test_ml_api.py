"""API integration tests for FastAPI ML endpoints."""

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


def test_get_models_overview() -> None:
    response = client.get("/api/v1/ml/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "anomaly" in data["models"]
    assert "classification" in data["models"]
    assert "severity" in data["models"]
    assert data["models"]["anomaly"]["active_version"] == "v1.0.0"


def test_post_anomaly_normal_telemetry() -> None:
    payload = {
        "service_id": "auth-service",
        "cpu_usage": 22.5,
        "memory_usage": 38.0,
        "disk_usage": 42.0,
        "network_traffic_kbps": 350.0,
        "request_count": 400,
        "latency_p95_ms": 35.0,
        "error_rate": 0.001,
        "active_connections": 25,
    }
    response = client.post("/api/v1/ml/anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["service_id"] == "auth-service"
    assert "anomaly_score" in data
    assert "is_anomaly" in data
    assert 0.0 <= data["anomaly_score"] <= 1.0
    assert data["model_version"] == "v1.0.0"


def test_post_anomaly_spike_telemetry() -> None:
    payload = {
        "service_id": "payment-service",
        "cpu_usage": 98.5,
        "memory_usage": 92.0,
        "disk_usage": 45.0,
        "network_traffic_kbps": 4500.0,
        "request_count": 2500,
        "latency_p95_ms": 4800.0,
        "error_rate": 0.75,
        "active_connections": 100,
    }
    response = client.post("/api/v1/ml/anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["service_id"] == "payment-service"
    assert data["anomaly_score"] > 0.4
    assert len(data["contributing_signals"]) > 0


def test_post_classify_incident_database() -> None:
    payload = {
        "title": "HikariPool Timeout in Payment Service",
        "symptoms": "HikariCP database connection pool timeout waiting for connection; active conns 100/100 limit reached; SQL execution timeout",
        "service_id": "payment-service",
        "tier": "critical",
        "active_connections": 100,
        "latency_p95_ms": 5000.0,
        "error_rate": 0.65,
    }
    response = client.post("/api/v1/ml/classify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "database"
    assert data["confidence"] > 0.5
    assert "database" in data["probabilities"]
    assert data["algorithm"] == "xgboost"


def test_post_classify_incident_network() -> None:
    payload = {
        "title": "Packet Loss and TCP Retransmission Degradation",
        "symptoms": "TCP socket packet retransmission rate elevated to 16%; network throughput dropped; MTU mismatch gateway packet dropping",
        "service_id": "notification-service",
        "tier": "standard",
        "error_rate": 0.28,
        "latency_p95_ms": 850.0,
    }
    response = client.post("/api/v1/ml/classify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "network"
    assert data["confidence"] > 0.5


def test_post_predict_severity_critical() -> None:
    payload = {
        "title": "Third-Party Payment Acquirer 503 Outage",
        "symptoms": "All credit card transactions failing with 503 Service Unavailable; checkout pipeline halted",
        "service_id": "payment-service",
        "tier": "critical",
        "error_rate": 0.88,
        "latency_p95_ms": 5000.0,
    }
    response = client.post("/api/v1/ml/severity", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["severity"] in ["CRITICAL", "HIGH"]
    assert len(data["risk_factors"]) > 0
    assert any("Critical-tier" in rf for rf in data["risk_factors"])


def test_post_anomaly_validation_error() -> None:
    # cpu_usage > 100.0 should trigger Pydantic ValidationError
    payload = {
        "service_id": "auth-service",
        "cpu_usage": 150.0,
        "memory_usage": 50.0,
        "disk_usage": 50.0,
        "network_traffic_kbps": 100.0,
        "request_count": 100,
        "latency_p95_ms": 10.0,
        "error_rate": 0.0,
        "active_connections": 10,
    }
    response = client.post("/api/v1/ml/anomaly", json=payload)
    assert response.status_code == 422
