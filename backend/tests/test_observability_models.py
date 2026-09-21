from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.deployment import Deployment
from app.models.incident import Incident
from app.models.log import LogEntry
from app.models.metric import Metric
from app.models.service import Service


@pytest.fixture
def in_memory_db() -> Session:
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(bind=test_engine)
    session = session_factory()
    yield session
    session.close()


def test_service_creation_and_relationships(in_memory_db: Session) -> None:
    now = datetime.now(timezone.utc)
    svc = Service(
        id="test-service",
        name="Test Service",
        tier="critical",
        owner_team="test-team",
    )
    in_memory_db.add(svc)
    in_memory_db.commit()

    # Add metric
    metric = Metric(
        service_id=svc.id,
        timestamp=now,
        cpu_usage=45.2,
        memory_usage=55.0,
        disk_usage=20.0,
        network_traffic_kbps=150.0,
        request_count=120,
        latency_p95_ms=32.5,
        error_rate=0.001,
        active_connections=12,
    )
    in_memory_db.add(metric)

    # Add log entry
    log = LogEntry(
        service_id=svc.id,
        timestamp=now,
        log_level="ERROR",
        message="Simulated connection timeout to database",
        trace_id="trace-123456",
        metadata_json={"http_status": 504},
    )
    in_memory_db.add(log)

    # Add deployment
    dep = Deployment(
        service_id=svc.id,
        version="v1.0.0",
        deployed_at=now,
        environment="production",
        status="SUCCESS",
        changelog="Initial release",
    )
    in_memory_db.add(dep)
    in_memory_db.commit()
    in_memory_db.refresh(dep)

    # Add incident linked to deployment
    inc = Incident(
        id="INC-TEST-001",
        service_id=svc.id,
        title="Test Outage",
        started_at=now,
        resolved_at=now,
        severity="P1_CRITICAL",
        symptoms="High latency",
        root_cause="Bad config",
        resolution="Hotfix applied",
        status="RESOLVED",
        incident_type="CPU_SATURATION",
        related_deployment_id=dep.id,
    )
    in_memory_db.add(inc)
    in_memory_db.commit()

    # Query back and verify relations
    fetched_svc = in_memory_db.get(Service, "test-service")
    assert fetched_svc is not None
    assert len(fetched_svc.metrics) == 1
    assert fetched_svc.metrics[0].cpu_usage == 45.2
    assert len(fetched_svc.logs) == 1
    assert fetched_svc.logs[0].trace_id == "trace-123456"
    assert len(fetched_svc.deployments) == 1
    assert len(fetched_svc.incidents) == 1
    assert fetched_svc.incidents[0].related_deployment.version == "v1.0.0"
