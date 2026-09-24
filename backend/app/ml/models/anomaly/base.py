"""Base Anomaly Detector abstraction for OpsPilot AI.

Defines the pluggable interface for unsupervised anomaly detection algorithms
such as Isolation Forest, One-Class SVM, or Local Outlier Factor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import joblib
import numpy as np


class BaseAnomalyDetector(ABC):
    """Abstract Base Class for pluggable observability anomaly detectors."""

    def __init__(self, name: str, algorithm: str) -> None:
        self.name = name
        self.algorithm = algorithm
        self.is_fitted: bool = False
        self.threshold_: float = 0.5

    @abstractmethod
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> BaseAnomalyDetector:
        """Fit the anomaly detector on the training feature matrix."""
        pass

    @abstractmethod
    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        """Compute continuous anomaly score in [0.0, 1.0], where 1.0 represents highest abnormality."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict binary anomaly flags (True for anomaly, False for normal)."""
        pass

    def save(self, filepath: str) -> None:
        """Persist detector artifact to disk."""
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath: str) -> BaseAnomalyDetector:
        """Load detector artifact from disk."""
        obj = joblib.load(filepath)
        if not isinstance(obj, BaseAnomalyDetector):
            raise TypeError(f"Loaded object is not a BaseAnomalyDetector: {type(obj)}")
        return obj
