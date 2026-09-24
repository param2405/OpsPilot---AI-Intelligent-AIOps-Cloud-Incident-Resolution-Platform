"""Integration tests for Deep Learning FastAPI endpoints."""

from fastapi.testclient import TestClient
import pytest

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_dl_model_info_endpoint(client: TestClient):
    response = client.get("/api/v1/ml/dl/model-info")
    assert response.status_code == 200
    data = response.json()
    assert "champion_architecture" in data
    assert data["champion_architecture"] in ("lstm", "gru")
    assert "vocab_size" in data
    assert "results" in data
    assert data["device"] == "cpu"


def test_dl_predict_sequence_endpoint(client: TestClient):
    payload = {
        "messages": [
            "Normal request GET /api/v1/orders HTTP 200 (latency=15ms)",
            "Active connections reached 80/100 cap on database pool",
            "HikariCP connection pool timeout waiting for connection (timeout=5000ms)",
            "Database transaction failed: connection unavailable",
        ],
        "service_id": "payment-service",
        "threshold": 0.50,
    }

    response = client.post("/api/v1/ml/dl/predict-sequence", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["service_id"] == "payment-service"
    assert "is_anomaly" in data
    assert isinstance(data["anomaly_probability"], float)
    assert 0.0 <= data["anomaly_probability"] <= 1.0
    assert len(data["attention_weights"]) == 4
    assert data["sequence_length"] == 4
    assert data["latency_ms"] >= 0.0

    # If attention attribution is present, verify top trigger event structure
    if data["top_trigger_event"]:
        trigger = data["top_trigger_event"]
        assert "log_message" in trigger
        assert "attention_weight" in trigger
        assert 0 <= trigger["index"] < 4


def test_dl_semantic_search_endpoint(client: TestClient):
    payload = {
        "query": "HikariCP connection pool exhaustion and timeout",
        "corpus_type": "runbooks",
        "top_k": 2,
    }

    response = client.post("/api/v1/ml/dl/semantic-search", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["query"] == payload["query"]
    assert len(data["results"]) == 2
    assert data["total_results"] == 2

    # First hit should be PostgreSQL pool runbook RB-001
    top_hit = data["results"][0]
    assert top_hit["id"] == "RB-001"
    assert "PostgreSQL" in top_hit["title"]
    assert top_hit["similarity_score"] > 0.0
    assert len(top_hit["steps"]) > 0
