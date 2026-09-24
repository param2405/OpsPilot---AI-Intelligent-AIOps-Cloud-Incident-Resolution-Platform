"""Unit tests for ML models (Isolation Forest, Incident Classifier, Severity Predictor)."""

import numpy as np
import pandas as pd
import pytest

from app.ml.data.corpus_generator import HistoricalIncidentCorpusGenerator
from app.ml.models.anomaly.isolation_forest import IsolationForestDetector, OneClassSVMDetector
from app.ml.models.classifier.incident_classifier import IncidentClassifierPipeline
from app.ml.models.severity.severity_predictor import SeverityPredictorPipeline


def test_isolation_forest_detector_scoring() -> None:
    rng = np.random.RandomState(42)
    # 200 normal points centered around 0.0 with std 1.0
    X_train = rng.normal(loc=0.0, scale=1.0, size=(200, 10))

    detector = IsolationForestDetector(n_estimators=50, contamination=0.05, random_state=42)
    detector.fit(X_train)

    assert detector.is_fitted

    # Test normal inlier
    inlier = np.zeros((1, 10))
    inlier_score = float(detector.compute_anomaly_scores(inlier)[0])
    assert 0.0 <= inlier_score <= 1.0

    # Test extreme outlier
    outlier = np.ones((1, 10)) * 50.0
    outlier_score = float(detector.compute_anomaly_scores(outlier)[0])
    outlier_pred = bool(detector.predict(outlier)[0])

    assert 0.0 <= outlier_score <= 1.0
    assert outlier_score > inlier_score
    assert outlier_pred is True


def test_one_class_svm_detector() -> None:
    rng = np.random.RandomState(42)
    X_train = rng.normal(loc=0.0, scale=1.0, size=(100, 8))

    detector = OneClassSVMDetector(nu=0.05)
    detector.fit(X_train)

    assert detector.is_fitted
    scores = detector.compute_anomaly_scores(X_train[:5])
    assert len(scores) == 5
    assert (scores >= 0.0).all() and (scores <= 1.0).all()


def test_incident_classifier_pipeline() -> None:
    generator = HistoricalIncidentCorpusGenerator(seed=42)
    df = generator.generate_corpus(n_samples=120)

    train_df = df.iloc[:90]
    test_df = df.iloc[90:]

    pipeline = IncidentClassifierPipeline(algorithm="xgboost", random_state=42)
    pipeline.fit(train_df)

    assert pipeline.is_fitted

    preds = pipeline.predict(test_df)
    assert len(preds) == len(test_df)

    single_res = pipeline.predict_single({
        "title": "PostgreSQL Connection Pool Exhaustion in payment-service",
        "symptoms": "HikariCP database connection pool timeout waiting for connection. Active DB connections reached 100/100 cap. Queries queued and timed out after 5000ms. Error rate spiked on database transactions.",
        "tier": "critical",
        "cpu_usage": 35.0,
        "memory_usage": 50.0,
        "disk_usage": 45.0,
        "network_traffic_kbps": 600.0,
        "request_count": 400,
        "active_connections": 100,
        "latency_p95_ms": 5000.0,
        "error_rate": 0.65,
    })
    assert single_res["category"] == "database"
    assert single_res["confidence"] > 0.0
    assert "database" in single_res["probabilities"]


def test_severity_predictor_pipeline() -> None:
    generator = HistoricalIncidentCorpusGenerator(seed=42)
    df = generator.generate_corpus(n_samples=120)

    train_df = df.iloc[:90]
    test_df = df.iloc[90:]

    pipeline = SeverityPredictorPipeline(n_estimators=50, random_state=42)
    pipeline.fit(train_df)

    assert pipeline.is_fitted

    preds = pipeline.predict(test_df)
    assert len(preds) == len(test_df)

    single_res = pipeline.predict_single({
        "title": "Catastrophic Service Outage",
        "symptoms": "Complete gateway failure returning 503 to all users",
        "tier": "critical",
        "error_rate": 0.85,
        "latency_p95_ms": 4000.0,
    })
    assert single_res["severity"] in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    assert len(single_res["risk_factors"]) > 0
