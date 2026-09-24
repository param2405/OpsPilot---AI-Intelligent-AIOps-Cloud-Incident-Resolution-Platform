"""Incident feature engineering pipeline for OpsPilot AI.

Extracts multimodal features combining textual symptoms/title (TF-IDF),
service metadata context (one-hot/ordinal encodings), and onset telemetry metrics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler


TELEMETRY_ONSET_COLUMNS = [
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "network_traffic_kbps",
    "request_count",
    "latency_p95_ms",
    "error_rate",
    "active_connections",
]

TIER_MAP = {
    "standard": 0.0,
    "high": 1.0,
    "critical": 2.0,
}


class IncidentFeaturePipeline(BaseEstimator, TransformerMixin):
    """Production multimodal feature pipeline for incident classification and severity prediction.
    
    Transforms:
      1. Text signals: TF-IDF vectorization of title and symptoms text.
      2. Service context: Numerical mapping of service tier criticality.
      3. Telemetry snapshot: Standard scaled metrics at time of incident onset.
    """

    def __init__(
        self,
        max_tfidf_features: int = 250,
        ngram_range: Tuple[int, int] = (1, 2),
    ) -> None:
        self.max_tfidf_features = max_tfidf_features
        self.ngram_range = ngram_range
        self.tfidf = TfidfVectorizer(
            max_features=max_tfidf_features,
            ngram_range=ngram_range,
            sublinear_tf=True,
            stop_words="english",
        )
        self.scaler = StandardScaler()
        self.feature_names_: List[str] = []
        self._is_fitted: bool = False

    @staticmethod
    def _combine_text(df: pd.DataFrame) -> List[str]:
        """Combine title and symptoms into a unified text document per record."""
        titles = df["title"].fillna("").astype(str) if "title" in df.columns else pd.Series([""] * len(df))
        symptoms = df["symptoms"].fillna("").astype(str) if "symptoms" in df.columns else pd.Series([""] * len(df))
        return (titles + " " + symptoms).str.strip().tolist()

    def _extract_numerical(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract and impute telemetry snapshot and tier context."""
        num_dict: Dict[str, Any] = {}
        for col in TELEMETRY_ONSET_COLUMNS:
            if col in df.columns:
                num_dict[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            else:
                num_dict[col] = pd.Series([0.0] * len(df), index=df.index)

        # Service tier criticality
        if "tier" in df.columns:
            num_dict["tier_weight"] = df["tier"].map(lambda t: TIER_MAP.get(str(t).lower(), 0.0)).fillna(0.0)
        else:
            num_dict["tier_weight"] = pd.Series([0.0] * len(df), index=df.index)

        return pd.DataFrame(num_dict, index=df.index)

    def fit(self, X: pd.DataFrame, y: Optional[Any] = None) -> IncidentFeaturePipeline:
        """Fit TF-IDF on symptom vocabulary and scaler on numerical metrics strictly on training set."""
        text_corpus = self._combine_text(X)
        self.tfidf.fit(text_corpus)

        num_df = self._extract_numerical(X)
        self.scaler.fit(num_df.values)

        tfidf_names = [f"tfidf_{w}" for w in self.tfidf.get_feature_names_out()]
        num_names = list(num_df.columns)
        self.feature_names_ = tfidf_names + num_names
        self._is_fitted = True
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Transform incidents into multimodal dense feature matrix."""
        if not self._is_fitted:
            raise RuntimeError("IncidentFeaturePipeline is not fitted yet.")

        text_corpus = self._combine_text(X)
        tfidf_sparse = self.tfidf.transform(text_corpus)
        tfidf_dense = tfidf_sparse.toarray()

        num_df = self._extract_numerical(X)
        num_scaled = self.scaler.transform(num_df.values)

        return np.hstack([tfidf_dense, num_scaled])

    def fit_transform(self, X: pd.DataFrame, y: Optional[Any] = None) -> np.ndarray:
        return self.fit(X, y).transform(X)

    def extract_single_incident(self, incident_dict: Dict[str, Any]) -> np.ndarray:
        """Feature extraction helper for online single-incident prediction."""
        df = pd.DataFrame([incident_dict])
        return self.transform(df)
