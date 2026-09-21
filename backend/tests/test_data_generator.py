import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.incident import Incident
from app.models.metric import Metric
from app.models.service import Service
from app.services.synthetic_data_generator import SyntheticDataGenerator


@pytest.fixture
def generator_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_generator_deterministic_output(generator_db: Session) -> None:
    generator1 = SyntheticDataGenerator(db=generator_db, seed=100)
    stats1 = generator1.generate(days=1, step_minutes=15)

    assert stats1["services"] == 6
    assert stats1["incidents"] == 7
    assert stats1["metrics"] > 0
    assert stats1["logs"] > 0

    # Verify incident patterns exist
    incidents = generator_db.query(Incident).all()
    assert len(incidents) == 7
    incident_types = {inc.incident_type for inc in incidents}
    assert "CPU_SATURATION" in incident_types
    assert "MEMORY_LEAK" in incident_types
    assert "DB_CONNECTION_EXHAUSTION" in incident_types
    assert "API_LATENCY_SPIKE" in incident_types
    assert "NETWORK_DEGRADATION" in incident_types
    assert "DEPLOYMENT_FAILURE" in incident_types
    assert "EXTERNAL_DEPENDENCY_FAILURE" in incident_types


def test_generator_temporal_incident_behavior(generator_db: Session) -> None:
    generator = SyntheticDataGenerator(db=generator_db, seed=42)
    generator.generate(days=1, step_minutes=5)

    # Auth service has CPU_SATURATION incident. Peak CPU should reach > 90%
    auth_metrics = generator_db.query(Metric).filter(Metric.service_id == "auth-service").all()
    max_cpu = max(m.cpu_usage for m in auth_metrics)
    assert max_cpu > 90.0, f"Expected CPU saturation > 90%, but got {max_cpu}"

    # Payment service has DB_CONNECTION_EXHAUSTION. Max connections should reach >= 95
    payment_metrics = generator_db.query(Metric).filter(Metric.service_id == "payment-service").all()
    max_conns = max(m.active_connections for m in payment_metrics)
    assert max_conns >= 95, f"Expected active connections >= 95, but got {max_conns}"
