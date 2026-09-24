"""Isolation Forest and pluggable anomaly detector implementations for OpsPilot AI.

Implements Isolation Forest as the primary algorithm with calibrated anomaly scores [0.0 - 1.0],
and provides an alternative One-Class SVM detector for architectural comparison.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.svm import OneClassSVM

from app.ml.models.anomaly.base import BaseAnomalyDetector


class IsolationForestDetector(BaseAnomalyDetector):
    """Production-grade Isolation Forest detector for time-series telemetry streams.
    
    Isolation Forest partitions points using random feature splits.
    Anomalies are isolated close to the root of the trees, resulting in noticeably
    shorter average path lengths.
    """

    def __init__(
        self,
        n_estimators: int = 150,
        contamination: float = 0.05,
        max_samples: float | int = "auto",
        random_state: int = 42,
    ) -> None:
        super().__init__(name="IsolationForest", algorithm="isolation_forest")
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.max_samples = max_samples
        self.random_state = random_state

        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            max_samples=self.max_samples,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._score_min: float = -0.5
        self._score_max: float = 0.5

    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> IsolationForestDetector:
        """Fit Isolation Forest on training telemetry feature matrix."""
        self.model.fit(X)
        self.is_fitted = True

        # Calibrate score range from training distribution
        raw_scores = self.model.decision_function(X)
        self._score_min = float(np.percentile(raw_scores, 1))
        self._score_max = float(np.percentile(raw_scores, 99))
        return self

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        """Compute calibrated continuous anomaly score in [0.0, 1.0].
        
        IsolationForest decision_function outputs negative values for outliers and positive for inliers.
        We invert and scale:
          score = (max - raw) / (max - min)
          Higher score -> Higher abnormality.
        """
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted before computing anomaly scores.")

        raw_scores = self.model.decision_function(X)
        # Avoid division by zero
        span = max(1e-6, self._score_max - self._score_min)
        # Invert: low decision_function -> high anomaly score
        normalized = (self._score_max - raw_scores) / span
        return np.clip(normalized, 0.0, 1.0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict boolean anomaly flags (True if anomaly, False if normal)."""
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted before predicting.")

        preds = self.model.predict(X)
        # IsolationForest returns -1 for outlier, 1 for inlier
        return preds == -1


class OneClassSVMDetector(BaseAnomalyDetector):
    """Alternative One-Class SVM detector for algorithm comparison."""

    def __init__(
        self,
        kernel: str = "rbf",
        gamma: str | float = "scale",
        nu: float = 0.05,
    ) -> None:
        super().__init__(name="OneClassSVM", algorithm="one_class_svm")
        self.kernel = kernel
        self.gamma = gamma
        self.nu = nu
        self.model = OneClassSVM(
            kernel=self.kernel,
            gamma=self.gamma,
            nu=self.nu,
        )
        self._score_min: float = -1.0
        self._score_max: float = 1.0

    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> OneClassSVMDetector:
        self.model.fit(X)
        self.is_fitted = True
        raw_scores = self.model.decision_function(X)
        self._score_min = float(np.percentile(raw_scores, 1))
        self._score_max = float(np.percentile(raw_scores, 99))
        return self

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted.")
        raw_scores = self.model.decision_function(X)
        span = max(1e-6, self._score_max - self._score_min)
        normalized = (self._score_max - raw_scores) / span
        return np.clip(normalized, 0.0, 1.0)

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Detector must be fitted.")
        preds = self.model.predict(X)
        return preds == -1
