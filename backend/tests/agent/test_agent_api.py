"""API integration tests for LangGraph agent endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_list_tools():
    response = client.get("/api/v1/agent/tools")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tools"] == 6
    assert data["mode"] == "read_only"
    names = [t["name"] for t in data["tools"]]
    assert "get_metrics" in names
    assert "search_runbooks" in names


def test_api_execute_tool_direct():
    payload = {
        "data": [10.0, 20.0, 30.0, 40.0],
        "metric_name": "latency",
    }
    response = client.post("/api/v1/agent/tools/calculate_statistics/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 4
    assert data["mean"] == 25.0


def test_api_investigate_endpoint():
    payload = {
        "service": "order-service",
        "title": "HikariCP database pool exhausted on order-service",
        "description": "Connection timeout after 30000ms. Active connections at 95% capacity.",
        "severity": "P1",
        "time_range": "1h",
    }
    response = client.post("/api/v1/agent/investigate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "order-service"
    assert data["has_sufficient_evidence"] is True
    assert "suspected_root_cause" in data
    assert len(data["evidence"]) > 0
    assert len(data["recommended_remediation"]) > 0
    assert len(data["sources"]) > 0
