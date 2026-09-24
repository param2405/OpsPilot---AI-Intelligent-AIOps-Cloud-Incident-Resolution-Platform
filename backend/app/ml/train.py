"""Production ML Training Pipeline for OpsPilot AI.

Orchestrates data extraction, chronological splitting, feature engineering,
model training, comprehensive evaluation, MLflow experiment tracking,
and model registry publishing for:
  1. Anomaly Detection (Isolation Forest vs One-Class SVM)
  2. Incident Classification (Logistic Regression Baseline vs XGBoost)
  3. Incident Severity Prediction (XGBoost Multimodal)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.ml.data.collector import ObservabilityDataCollector
from app.ml.data.corpus_generator import HistoricalIncidentCorpusGenerator
from app.ml.data.splitter import ChronologicalSplitter, IncidentSplitter
from app.ml.features.incident import IncidentFeaturePipeline
from app.ml.features.telemetry import TelemetryFeaturePipeline
from app.ml.models.anomaly.isolation_forest import IsolationForestDetector, OneClassSVMDetector
from app.ml.models.classifier.incident_classifier import IncidentClassifierPipeline
from app.ml.models.severity.severity_predictor import SeverityPredictorPipeline
from app.ml.registry.model_registry import ModelRegistry
from app.ml.tracking.mlflow_manager import MLflowTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ml_train")


def train_anomaly_detection(
    version: str = "v1.0.0",
    track_mlflow: bool = True,
    seed: int = 42,
) -> Dict[str, Any]:
    """Train and evaluate telemetry anomaly detection pipeline."""
    logger.info("=== 1. Training Anomaly Detection Engine ===")
    collector = ObservabilityDataCollector()
    df = collector.load_telemetry_with_ground_truth()
    logger.info("Loaded %d telemetry records from database.", len(df))

    # Chronological Split (70% train, 15% val, 15% test)
    splitter = ChronologicalSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df = splitter.split(df)
    logger.info(
        "Chronological split: Train=%d (%s to %s), Val=%d, Test=%d (%s to %s)",
        len(train_df),
        train_df["timestamp"].min(),
        train_df["timestamp"].max(),
        len(val_df),
        len(test_df),
        test_df["timestamp"].min(),
        test_df["timestamp"].max(),
    )

    # Feature Engineering (strictly fit on train_df)
    pipeline = TelemetryFeaturePipeline(rolling_windows=(3, 6))
    X_train = pipeline.fit_transform(train_df)
    X_test = pipeline.transform(test_df)
    y_test = test_df["is_anomaly"].values

    # Train Isolation Forest
    logger.info("Fitting Isolation Forest detector...")
    iso_detector = IsolationForestDetector(n_estimators=150, contamination=0.06, random_state=seed)
    iso_detector.fit(X_train)

    # Evaluate on held-out test split
    iso_scores = iso_detector.compute_anomaly_scores(X_test)
    iso_preds = iso_detector.predict(X_test)

    # Test metrics
    iso_prec = float(precision_score(y_test, iso_preds, zero_division=0))
    iso_rec = float(recall_score(y_test, iso_preds, zero_division=0))
    iso_f1 = float(f1_score(y_test, iso_preds, zero_division=0))
    iso_roc = float(roc_auc_score(y_test, iso_scores)) if len(np.unique(y_test)) > 1 else 0.0
    iso_pr_auc = float(average_precision_score(y_test, iso_scores)) if len(np.unique(y_test)) > 1 else 0.0

    iso_metrics = {
        "precision": round(iso_prec, 4),
        "recall": round(iso_rec, 4),
        "f1": round(iso_f1, 4),
        "roc_auc": round(iso_roc, 4),
        "pr_auc": round(iso_pr_auc, 4),
        "test_anomalies_detected": int(iso_preds.sum()),
        "test_ground_truth_anomalies": int(y_test.sum()),
    }
    logger.info("Isolation Forest Test Metrics: %s", iso_metrics)

    # Train One-Class SVM for algorithm comparison
    logger.info("Fitting One-Class SVM for algorithm comparison...")
    svm_detector = OneClassSVMDetector(nu=0.06)
    svm_detector.fit(X_train)
    svm_scores = svm_detector.compute_anomaly_scores(X_test)
    svm_preds = svm_detector.predict(X_test)

    svm_metrics = {
        "precision": round(float(precision_score(y_test, svm_preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, svm_preds, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, svm_preds, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, svm_scores)) if len(np.unique(y_test)) > 1 else 0.0, 4),
        "pr_auc": round(float(average_precision_score(y_test, svm_scores)) if len(np.unique(y_test)) > 1 else 0.0, 4),
    }
    logger.info("One-Class SVM Test Metrics: %s", svm_metrics)

    # MLflow logging
    mlflow_run_id = None
    if track_mlflow:
        tracker = MLflowTracker()
        mlflow_run_id = tracker.log_model_run(
            experiment_key="anomaly",
            run_name=f"isolation_forest_{version}",
            params={
                "algorithm": "isolation_forest",
                "n_estimators": 150,
                "contamination": 0.06,
                "rolling_windows": "(3, 6)",
                "scaler": "RobustScaler",
                "train_size": len(train_df),
                "test_size": len(test_df),
            },
            metrics=iso_metrics,
            tags={"model_type": "anomaly_detection", "version": version},
        )
        # Log comparison run
        tracker.log_model_run(
            experiment_key="anomaly",
            run_name=f"one_class_svm_{version}",
            params={"algorithm": "one_class_svm", "nu": 0.06, "kernel": "rbf"},
            metrics=svm_metrics,
            tags={"model_type": "anomaly_detection_comparison", "version": version},
        )

    # Publish champion (Isolation Forest) to Model Registry
    registry = ModelRegistry()
    registry.register_model(
        model_name="anomaly",
        version=version,
        algorithm="isolation_forest",
        model_obj=iso_detector,
        metrics=iso_metrics,
        mlflow_run_id=mlflow_run_id,
        feature_pipeline=pipeline,
        set_active=True,
    )
    logger.info("Registered active anomaly detector version %s in registry.", version)
    return iso_metrics


def train_incident_classification(
    version: str = "v1.0.0",
    track_mlflow: bool = True,
    seed: int = 42,
) -> Dict[str, Any]:
    """Train and compare Logistic Regression baseline vs XGBoost classifier."""
    logger.info("=== 2. Training Incident Classification Engine ===")
    generator = HistoricalIncidentCorpusGenerator(seed=seed)
    df = generator.generate_corpus(n_samples=1200)
    logger.info("Synthesized %d historical incident postmortems.", len(df))

    # Chronological Split
    splitter = IncidentSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df = splitter.split(df)

    # 1. Baseline: Logistic Regression
    logger.info("Fitting Logistic Regression baseline classifier...")
    lr_pipeline = IncidentClassifierPipeline(algorithm="logistic_regression", random_state=seed)
    lr_pipeline.fit(train_df)
    lr_metrics = lr_pipeline.evaluate(test_df)
    logger.info("Logistic Regression Test Metrics: %s", {k: v for k, v in lr_metrics.items() if k != "confusion_matrix"})

    # 2. Challenger: XGBoost
    logger.info("Fitting XGBoost gradient-boosted tree classifier...")
    xgb_pipeline = IncidentClassifierPipeline(algorithm="xgboost", random_state=seed)
    xgb_pipeline.fit(train_df)
    xgb_metrics = xgb_pipeline.evaluate(test_df)
    logger.info("XGBoost Test Metrics: %s", {k: v for k, v in xgb_metrics.items() if k != "confusion_matrix"})

    # Select champion based on Macro F1
    champion_pipeline = xgb_pipeline if xgb_metrics["macro_f1"] >= lr_metrics["macro_f1"] else lr_pipeline
    champion_algo = champion_pipeline.algorithm
    champion_metrics = xgb_metrics if champion_algo == "xgboost" else lr_metrics
    logger.info("Selected Champion Algorithm: %s (Macro F1 = %f)", champion_algo, champion_metrics["macro_f1"])

    mlflow_run_id = None
    if track_mlflow:
        tracker = MLflowTracker()
        # Log baseline
        tracker.log_model_run(
            experiment_key="classification",
            run_name=f"logistic_regression_baseline_{version}",
            params={"algorithm": "logistic_regression", "C": 1.0, "max_iter": 1000, "class_weight": "balanced"},
            metrics={k: v for k, v in lr_metrics.items() if isinstance(v, (int, float))},
            tags={"model_type": "incident_classification", "tier": "baseline"},
        )
        # Log challenger & champion
        mlflow_run_id = tracker.log_model_run(
            experiment_key="classification",
            run_name=f"xgboost_challenger_{version}",
            params={"algorithm": "xgboost", "n_estimators": 100, "max_depth": 4, "learning_rate": 0.1},
            metrics={k: v for k, v in xgb_metrics.items() if isinstance(v, (int, float))},
            tags={"model_type": "incident_classification", "tier": "champion" if champion_algo == "xgboost" else "challenger"},
        )

    # Publish champion to registry
    registry = ModelRegistry()
    registry.register_model(
        model_name="classification",
        version=version,
        algorithm=champion_algo,
        model_obj=champion_pipeline,
        metrics=champion_metrics,
        mlflow_run_id=mlflow_run_id,
        set_active=True,
    )
    logger.info("Registered active incident classifier version %s in registry.", version)
    return champion_metrics


def train_severity_prediction(
    version: str = "v1.0.0",
    track_mlflow: bool = True,
    seed: int = 42,
) -> Dict[str, Any]:
    """Train and evaluate incident severity prediction pipeline."""
    logger.info("=== 3. Training Incident Severity Prediction Engine ===")
    generator = HistoricalIncidentCorpusGenerator(seed=seed)
    df = generator.generate_corpus(n_samples=1200)

    splitter = IncidentSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df = splitter.split(df)

    logger.info("Fitting Severity Predictor (XGBoost Multimodal)...")
    sev_pipeline = SeverityPredictorPipeline(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.08,
        random_state=seed,
    )
    sev_pipeline.fit(train_df)
    sev_metrics = sev_pipeline.evaluate(test_df)
    logger.info("Severity Predictor Test Metrics: %s", {k: v for k, v in sev_metrics.items() if k != "confusion_matrix"})

    mlflow_run_id = None
    if track_mlflow:
        tracker = MLflowTracker()
        mlflow_run_id = tracker.log_model_run(
            experiment_key="severity",
            run_name=f"severity_xgboost_{version}",
            params={"algorithm": "xgboost", "n_estimators": 120, "max_depth": 4, "learning_rate": 0.08},
            metrics={k: v for k, v in sev_metrics.items() if isinstance(v, (int, float))},
            tags={"model_type": "severity_prediction", "version": version},
        )

    registry = ModelRegistry()
    registry.register_model(
        model_name="severity",
        version=version,
        algorithm="xgboost",
        model_obj=sev_pipeline,
        metrics=sev_metrics,
        mlflow_run_id=mlflow_run_id,
        set_active=True,
    )
    logger.info("Registered active severity predictor version %s in registry.", version)
    return sev_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train OpsPilot AI Machine Learning Models.")
    parser.add_argument(
        "--model",
        type=str,
        default="all",
        choices=["all", "anomaly", "classification", "severity"],
        help="Model pipeline to train (default: all)",
    )
    parser.add_argument("--version", type=str, default="v1.0.0", help="Model version tag (default: v1.0.0)")
    parser.add_argument("--no-mlflow", action="store_true", help="Disable MLflow experiment tracking")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    args = parser.parse_args()

    track_mlflow = not args.no_mlflow

    if args.model in ("all", "anomaly"):
        train_anomaly_detection(version=args.version, track_mlflow=track_mlflow, seed=args.seed)

    if args.model in ("all", "classification"):
        train_incident_classification(version=args.version, track_mlflow=track_mlflow, seed=args.seed)

    if args.model in ("all", "severity"):
        train_severity_prediction(version=args.version, track_mlflow=track_mlflow, seed=args.seed)

    logger.info("All requested ML pipelines executed and registered successfully.")


if __name__ == "__main__":
    main()
