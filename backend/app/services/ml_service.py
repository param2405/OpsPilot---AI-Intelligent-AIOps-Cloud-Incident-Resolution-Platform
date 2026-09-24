"""ML Inference and Lifecycle Service for OpsPilot AI.

Decouples machine learning models from API transport layers, formatting predictions,
scoring feature contributions, and coordinating model version retrieval.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np

from app.ml.models.classifier.incident_classifier import IncidentClassifierPipeline
from app.ml.models.severity.severity_predictor import SeverityPredictorPipeline
from app.ml.registry.model_registry import ModelRegistry
from app.schemas.ml import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    IncidentClassificationRequest,
    IncidentClassificationResponse,
    ModelsOverviewResponse,
    RetrainRequest,
    RetrainResponse,
    SeverityPredictionRequest,
    SeverityPredictionResponse,
)


class MLInferenceService:
    """Production ML inference engine interfacing with the model registry."""

    def __init__(self, registry: Optional[ModelRegistry] = None) -> None:
        self.registry = registry or ModelRegistry()

    def detect_anomaly(self, req: AnomalyDetectionRequest) -> AnomalyDetectionResponse:
        """Detect operational anomalies on incoming telemetry stream."""
        info = self.registry.get_active_model_info("anomaly")
        if not info:
            raise RuntimeError("Anomaly detector model is not available. Please train models first.")

        model, feature_pipeline = self.registry.load_active_model("anomaly")
        if feature_pipeline is None:
            raise RuntimeError("Telemetry feature pipeline missing from registry.")

        # Prepare payload dictionary
        metric_dict = {
            "service_id": req.service_id,
            "timestamp": req.timestamp or datetime.now(timezone.utc),
            "cpu_usage": req.cpu_usage,
            "memory_usage": req.memory_usage,
            "disk_usage": req.disk_usage,
            "network_traffic_kbps": req.network_traffic_kbps,
            "request_count": req.request_count,
            "latency_p95_ms": req.latency_p95_ms,
            "error_rate": req.error_rate,
            "active_connections": req.active_connections,
        }

        history_dicts = None
        if req.recent_history:
            history_dicts = [
                {
                    "service_id": req.service_id,
                    "timestamp": h.timestamp or datetime.now(timezone.utc),
                    "cpu_usage": h.cpu_usage,
                    "memory_usage": h.memory_usage,
                    "disk_usage": h.disk_usage,
                    "network_traffic_kbps": h.network_traffic_kbps,
                    "request_count": h.request_count,
                    "latency_p95_ms": h.latency_p95_ms,
                    "error_rate": h.error_rate,
                    "active_connections": h.active_connections,
                }
                for h in req.recent_history
            ]

        X_point = feature_pipeline.extract_single_point(metric_dict, recent_history=history_dicts)

        anomaly_score = float(model.compute_anomaly_scores(X_point)[0])
        is_anomaly = bool(model.predict(X_point)[0])

        # Identify contributing signals based on metric thresholds and standardized features
        contributing_signals: List[str] = []
        if req.cpu_usage > 80.0:
            contributing_signals.append(f"High CPU utilization ({req.cpu_usage}%)")
        if req.memory_usage > 85.0:
            contributing_signals.append(f"High memory utilization ({req.memory_usage}%)")
        if req.error_rate > 0.05:
            contributing_signals.append(f"Elevated error rate ({round(req.error_rate * 100, 2)}%)")
        if req.latency_p95_ms > 1000.0:
            contributing_signals.append(f"Elevated p95 latency ({round(req.latency_p95_ms, 1)}ms)")
        if req.active_connections > 80:
            contributing_signals.append(f"High connection pool load ({req.active_connections} active conns)")

        if is_anomaly and not contributing_signals:
            contributing_signals.append("Multivariate anomaly across correlated rolling metric dynamics")

        return AnomalyDetectionResponse(
            service_id=req.service_id,
            timestamp=req.timestamp or datetime.now(timezone.utc),
            anomaly_score=round(anomaly_score, 4),
            is_anomaly=is_anomaly,
            contributing_signals=contributing_signals,
            model_version=info["version"],
            algorithm=info["algorithm"],
        )

    def classify_incident(self, req: IncidentClassificationRequest) -> IncidentClassificationResponse:
        """Classify operational incident into root failure domain."""
        info = self.registry.get_active_model_info("classification")
        if not info:
            raise RuntimeError("Incident classification model is not available. Please train models first.")

        pipeline: IncidentClassifierPipeline = self.registry.load_active_model("classification")[0]
        result = pipeline.predict_single(req.model_dump())

        return IncidentClassificationResponse(
            category=result["category"],
            confidence=result["confidence"],
            probabilities=result["probabilities"],
            model_version=info["version"],
            algorithm=info["algorithm"],
        )

    def predict_severity(self, req: SeverityPredictionRequest) -> SeverityPredictionResponse:
        """Predict incident severity level and highlight contributing risk factors."""
        info = self.registry.get_active_model_info("severity")
        if not info:
            raise RuntimeError("Severity prediction model is not available. Please train models first.")

        pipeline: SeverityPredictorPipeline = self.registry.load_active_model("severity")[0]
        result = pipeline.predict_single(req.model_dump())

        return SeverityPredictionResponse(
            severity=result["severity"],
            confidence=result["confidence"],
            probabilities=result["probabilities"],
            risk_factors=result["risk_factors"],
            model_version=info["version"],
            algorithm=info["algorithm"],
        )

    def get_models_overview(self) -> ModelsOverviewResponse:
        """Retrieve active models and manifest metadata."""
        return ModelsOverviewResponse(models=self.registry.list_models())

    def retrain(self, req: RetrainRequest) -> RetrainResponse:
        """Trigger synchronous or background model retraining."""
        from app.ml.train import (
            train_anomaly_detection,
            train_incident_classification,
            train_severity_prediction,
        )

        version = req.version or f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        results: Dict[str, Any] = {}

        if req.model in ("all", "anomaly"):
            results["anomaly"] = train_anomaly_detection(version=version, track_mlflow=True)
        if req.model in ("all", "classification"):
            results["classification"] = train_incident_classification(version=version, track_mlflow=True)
        if req.model in ("all", "severity"):
            results["severity"] = train_severity_prediction(version=version, track_mlflow=True)

        return RetrainResponse(
            status="SUCCESS",
            message=f"Retrained requested models ({req.model}) to version {version}",
            results=results,
        )
