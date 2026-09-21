from collections.abc import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.synthetic_data_generator import SyntheticDataGenerator


from sqlalchemy.pool import StaticPool


@pytest.fixture
def api_test_db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    # Seed data
    generator = SyntheticDataGenerator(db=session, seed=42)
    generator.generate(days=1, step_minutes=15)

    def _override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield session
    app.dependency_overrides.clear()
    session.close()


def test_api_list_services(api_test_db: Session) -> None:
    client = TestClient(app)
    res = client.get("/api/v1/services")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 6
    service_ids = [s["id"] for s in data]
    assert "api-gateway" in service_ids
    assert "auth-service" in service_ids


def test_api_get_service_by_id(api_test_db: Session) -> None:
    client = TestClient(app)
    res = client.get("/api/v1/services/auth-service")
    assert res.status_code == 200
    assert res.json()["name"] == "Authentication Service"

    not_found = client.get("/api/v1/services/non-existent-service")
    assert not_found.status_code == 404


def test_api_query_metrics_and_summary(api_test_db: Session) -> None:
    client = TestClient(app)
    res = client.get("/api/v1/metrics?service_id=auth-service&limit=10")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 10
    assert items[0]["service_id"] == "auth-service"

    summary_res = client.get("/api/v1/metrics/summary?service_id=auth-service")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["service_id"] == "auth-service"
    assert summary["sample_count"] > 0
    assert summary["max_cpu_usage"] > 80.0


def test_api_query_logs(api_test_db: Session) -> None:
    client = TestClient(app)
    res = client.get("/api/v1/logs?log_level=ERROR&limit=5")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    assert all(l["log_level"] == "ERROR" for l in logs)

    search_res = client.get("/api/v1/logs?search=database")
    assert search_res.status_code == 200


def test_api_query_deployments(api_test_db: Session) -> None:
    client = TestClient(app)
    res = client.get("/api/v1/deployments")
    assert res.status_code == 200
    deps = res.json()
    assert len(deps) > 0


def test_api_query_and_get_incidents(api_test_db: Session) -> None:
    client = TestClient(app)
    res = client.get("/api/v1/incidents?severity=P1_CRITICAL")
    assert res.status_code == 200
    incidents = res.json()
    assert len(incidents) > 0
    assert all(i["severity"] == "P1_CRITICAL" for i in incidents)

    inc_id = incidents[0]["id"]
    single_res = client.get(f"/api/v1/incidents/{inc_id}")
    assert single_res.status_code == 200
    assert single_res.json()["id"] == inc_id
    assert "symptoms" in single_res.json()
    assert "root_cause" in single_res.json()
