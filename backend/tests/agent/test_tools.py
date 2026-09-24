"""Unit tests for the 6 safe read-only SRE investigation tools."""

from __future__ import annotations

import pytest
from app.agent.tools.deployments_tool import get_recent_deployments
from app.agent.tools.historical_tool import search_historical_incidents
from app.agent.tools.logs_tool import search_logs
from app.agent.tools.metrics_tool import get_metrics, parse_time_range
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.runbooks_tool import search_runbooks
from app.agent.tools.statistics_tool import calculate_statistics
from app.db.session import SessionLocal


@pytest.fixture(scope="module")
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_get_metrics_tool(db_session):
    out = get_metrics(service="order-service", time_range="1h", db=db_session)
    assert out.status == "success"
    assert out.service == "order-service"
    assert "cpu_usage" in out.metrics
    assert "active_connections" in out.metrics
    assert len(out.trends) > 0


def test_parse_time_range_boundaries():
    assert parse_time_range("15m").total_seconds() == 900
    assert parse_time_range("1h").total_seconds() == 3600
    assert parse_time_range("24h").total_seconds() == 86400
    # Safe boundary: cap at 7 days
    assert parse_time_range("30d").total_seconds() == 7 * 86400


def test_search_logs_tool(db_session):
    out = search_logs(service="order-service", query="pool", time_range="1h", limit=10, db=db_session)
    assert out.status == "success"
    assert out.service == "order-service"
    assert out.total_found > 0
    assert len(out.logs) <= 10
    assert out.logs[0].level in ("INFO", "WARN", "ERROR", "FATAL")


def test_search_historical_incidents_tool(db_session):
    out = search_historical_incidents(query="payment gateway cascading timeout outage", limit=3, db=db_session)
    assert out.status == "success"
    assert out.total_matches > 0
    assert len(out.incidents) <= 3
    first_match = out.incidents[0]
    assert first_match.similarity_score > 0.0
    assert first_match.root_cause_summary is not None


def test_search_runbooks_tool(db_session):
    out = search_runbooks(query="PostgreSQL connection pool exhaustion HikariCP", service="postgres", limit=3, db=db_session)
    assert out.status == "success"
    assert out.total_matches > 0
    first_rb = out.runbooks[0]
    assert first_rb.relevance_score > 0.0
    assert len(first_rb.diagnostic_commands) > 0 or len(first_rb.remediation_steps) > 0


def test_get_recent_deployments_tool(db_session):
    out = get_recent_deployments(service="order-service", limit=5, db=db_session)
    assert out.status == "success"
    assert len(out.deployments) > 0
    assert out.deployments[0].revision is not None


def test_calculate_statistics_tool():
    data = [10.0, 12.0, 11.5, 9.8, 10.2, 55.0]  # Contains extreme spike 55.0
    out = calculate_statistics(data=data, metric_name="cpu_spikes")
    assert out.status == "success"
    assert out.count == 6
    assert out.min == 9.8
    assert out.max == 55.0
    assert out.mean > 10.0
    assert out.anomaly_detected is True


def test_tool_registry():
    specs = ToolRegistry.get_tool_specs()
    assert len(specs) == 6
    names = [s["name"] for s in specs]
    assert "get_metrics" in names
    assert "search_logs" in names
    assert "search_historical_incidents" in names
    assert "search_runbooks" in names
    assert "get_recent_deployments" in names
    assert "calculate_statistics" in names

    # Test safe execution
    res = ToolRegistry.execute_tool(
        tool_name="calculate_statistics",
        arguments={"data": [1.0, 2.0, 3.0]},
    )
    assert res.count == 3
    assert res.mean == 2.0
