"""Unit tests for feature engineering pipelines (telemetry and incident)."""

from datetime import datetime, timedelta, timezone
import numpy as np
import pandas as pd
import pytest

from app.ml.features.incident import IncidentFeaturePipeline
from app.ml.features.telemetry import TelemetryFeaturePipeline


def test_telemetry_feature_pipeline_extraction() -> None:
    now = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    data = []
    for i in range(10):
        data.append({
            "service_id": "test-svc",
            "timestamp": now + timedelta(minutes=5 * i),
            "cpu_usage": 20.0 + i,
            "memory_usage": 40.0 + i,
            "disk_usage": 50.0,
            "network_traffic_kbps": 300.0,
            "request_count": 500,
            "latency_p95_ms": 30.0 + 5 * i,
            "error_rate": 0.001 * i,
            "active_connections": 20 + i,
        })
    df = pd.DataFrame(data)

    pipeline = TelemetryFeaturePipeline(rolling_windows=(3, 6))
    features_df = pipeline.extract_features(df, is_training=True)

    # Check base columns
    assert "cpu_usage" in features_df.columns
    assert "memory_usage" in features_df.columns

    # Check temporal cyclical columns
    assert "sin_hour" in features_df.columns
    assert "cos_hour" in features_df.columns

    # Check rolling statistics
    assert "cpu_usage_roll_mean_3" in features_df.columns
    assert "cpu_usage_roll_std_3" in features_df.columns
    assert "latency_p95_ms_roll_mean_6" in features_df.columns

    # Check rate-of-change (first differences)
    assert "cpu_usage_delta" in features_df.columns
    assert "error_rate_delta" in features_df.columns

    # Check fit and transform
    X = pipeline.fit_transform(df)
    assert isinstance(X, np.ndarray)
    assert X.shape[0] == 10
    assert X.shape[1] == len(features_df.columns)


def test_telemetry_single_point_inference() -> None:
    now = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    history = [
        {
            "service_id": "svc-a",
            "timestamp": now - timedelta(minutes=10),
            "cpu_usage": 25.0,
            "memory_usage": 40.0,
            "disk_usage": 50.0,
            "network_traffic_kbps": 300.0,
            "request_count": 500,
            "latency_p95_ms": 30.0,
            "error_rate": 0.001,
            "active_connections": 20,
        },
        {
            "service_id": "svc-a",
            "timestamp": now - timedelta(minutes=5),
            "cpu_usage": 30.0,
            "memory_usage": 42.0,
            "disk_usage": 50.0,
            "network_traffic_kbps": 310.0,
            "request_count": 510,
            "latency_p95_ms": 32.0,
            "error_rate": 0.002,
            "active_connections": 22,
        },
    ]
    curr = {
        "service_id": "svc-a",
        "timestamp": now,
        "cpu_usage": 85.0,
        "memory_usage": 70.0,
        "disk_usage": 50.0,
        "network_traffic_kbps": 900.0,
        "request_count": 800,
        "latency_p95_ms": 1500.0,
        "error_rate": 0.35,
        "active_connections": 95,
    }

    pipeline = TelemetryFeaturePipeline(rolling_windows=(3, 6))
    pipeline.fit(pd.DataFrame(history))

    X_single = pipeline.extract_single_point(curr, recent_history=history)
    assert isinstance(X_single, np.ndarray)
    assert X_single.shape == (1, len(pipeline.feature_names_))


def test_incident_feature_pipeline() -> None:
    incidents = pd.DataFrame([
        {
            "title": "PostgreSQL Connection Pool Saturation",
            "symptoms": "HikariPool timeout waiting for connection; active DB conns 100/100",
            "tier": "critical",
            "cpu_usage": 45.0,
            "memory_usage": 60.0,
            "disk_usage": 40.0,
            "network_traffic_kbps": 400.0,
            "request_count": 500,
            "latency_p95_ms": 5000.0,
            "error_rate": 0.65,
            "active_connections": 100,
        },
        {
            "title": "OutOfMemoryError in Order Dispatcher",
            "symptoms": "Java heap space exhausted; exit code 137 SIGKILL",
            "tier": "high",
            "cpu_usage": 90.0,
            "memory_usage": 98.0,
            "disk_usage": 40.0,
            "network_traffic_kbps": 300.0,
            "request_count": 450,
            "latency_p95_ms": 800.0,
            "error_rate": 0.15,
            "active_connections": 25,
        },
    ])

    pipeline = IncidentFeaturePipeline(max_tfidf_features=50)
    X = pipeline.fit_transform(incidents)

    assert isinstance(X, np.ndarray)
    assert X.shape[0] == 2
    assert X.shape[1] > 0

    # Single point helper
    single_X = pipeline.extract_single_incident({
        "title": "CoreDNS Timeout",
        "symptoms": "i/o timeout resolving dns names",
        "tier": "standard",
    })
    assert single_X.shape == (1, X.shape[1])
