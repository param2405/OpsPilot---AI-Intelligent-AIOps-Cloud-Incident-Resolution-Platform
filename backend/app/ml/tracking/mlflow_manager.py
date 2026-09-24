"""MLflow Experiment Tracking and Metrics Logging for OpsPilot AI.

Manages experiment lifecycles, runs, hyperparameters, real evaluation metrics,
and model artifacts using local SQLite or filesystem tracking.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import mlflow


os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"


class MLflowTracker:
    """Manages experiment tracking, hyperparameter logging, and metric recording via MLflow."""

    EXPERIMENTS = {
        "anomaly": "opspilot-anomaly-detection",
        "classification": "opspilot-incident-classification",
        "severity": "opspilot-severity-prediction",
    }

    def __init__(self, tracking_uri: Optional[str] = None) -> None:
        if tracking_uri is None:
            # Default to backend/mlruns or local sqlite in backend
            base_dir = Path(__file__).resolve().parents[3]  # backend directory
            db_path = base_dir / "mlflow.db"
            self.tracking_uri = f"sqlite:///{db_path}"
        else:
            self.tracking_uri = tracking_uri

        mlflow.set_tracking_uri(self.tracking_uri)

    def get_or_create_experiment(self, experiment_key: str) -> str:
        """Ensure experiment exists and return its experiment_id."""
        exp_name = self.EXPERIMENTS.get(experiment_key, experiment_key)
        experiment = mlflow.get_experiment_by_name(exp_name)
        if experiment is not None:
            return experiment.experiment_id
        return mlflow.create_experiment(exp_name)

    def log_model_run(
        self,
        experiment_key: str,
        run_name: str,
        params: Dict[str, Any],
        metrics: Dict[str, float],
        artifacts: Optional[Dict[str, str]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> str:
        """Log a complete training run with parameters, actual metrics, and artifacts.
        
        Returns:
            The MLflow run_id.
        """
        exp_id = self.get_or_create_experiment(experiment_key)

        with mlflow.start_run(experiment_id=exp_id, run_name=run_name) as run:
            run_id = run.info.run_id

            # Log parameters
            for k, v in params.items():
                mlflow.log_param(k, v)

            # Log metrics (must be numerical floats/ints)
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, float(v))

            # Log tags
            if tags:
                mlflow.set_tags(tags)

            # Log artifacts if provided (paths to files)
            if artifacts:
                for art_name, art_path in artifacts.items():
                    if Path(art_path).exists():
                        mlflow.log_artifact(art_path, artifact_path=art_name)

            return run_id
