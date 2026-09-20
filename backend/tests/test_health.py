from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from tests.conftest import override_db


def test_root_points_to_health(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["phase"] == "1-foundation"
    assert body["health"] == "/api/v1/health"


def test_liveness_does_not_require_database(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert "service" in body
    assert "environment" in body


def test_readiness_ok_when_database_accepts_query(client: TestClient, ready_db) -> None:
    override_db(ready_db)
    try:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["database"]["connected"] is True
    finally:
        app.dependency_overrides.clear()


def test_readiness_unavailable_when_database_fails(client: TestClient, unavailable_db) -> None:
    override_db(unavailable_db)
    try:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unavailable"
        assert body["database"]["connected"] is False
    finally:
        app.dependency_overrides.clear()
