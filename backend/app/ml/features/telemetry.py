"""Telemetry time-series feature engineering pipeline for OpsPilot AI.

Transforms raw observability metrics (CPU, memory, disk, network, latency, error rate, etc.)
into rich feature matrices with rolling statistics, rate-of-change deltas, and cyclical temporal encodings.
Guarantees strict leakage prevention by computing transforms chronologically per service and
fitting scalers exclusively on the training partition.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import RobustScaler


RAW_TELEMETRY_COLUMNS = [
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "network_traffic_kbps",
    "request_count",
    "latency_p95_ms",
    "error_rate",
    "active_connections",
]

ROLLING_TARGET_COLUMNS = [
    "cpu_usage",
    "memory_usage",
    "latency_p95_ms",
    "error_rate",
    "network_traffic_kbps",
]


class TelemetryFeaturePipeline(BaseEstimator, TransformerMixin):
    """Production feature engineering pipeline for microservice telemetry streams.
    
    Features engineered:
      1. Base telemetry metrics: 8 raw metrics.
      2. Temporal cyclical features: sin_hour, cos_hour (continuous 24-hour diurnal cycle).
      3. Rolling statistics: rolling mean and std over short (15m = 3 steps) and medium (30m = 6 steps) windows.
      4. Rate of change (delta): first difference (x_t - x_{t-1}) for key volatile metrics.
      5. Robust scaling: fitted strictly on training data to prevent data leakage.
    """

    def __init__(
        self,
        rolling_windows: Tuple[int, ...] = (3, 6),
        scaler: Optional[BaseEstimator] = None,
    ) -> None:
        self.rolling_windows = rolling_windows
        self.scaler = scaler if scaler is not None else RobustScaler()
        self.feature_names_: List[str] = []
        self._is_fitted: bool = False

    @staticmethod
    def _compute_cyclical_time(timestamps: pd.Series) -> pd.DataFrame:
        """Encode timestamp into continuous cyclical sin/cos hour components."""
        dt = pd.to_datetime(timestamps, utc=True)
        hour_fraction = dt.dt.hour + dt.dt.minute / 60.0 + dt.dt.second / 3600.0
        sin_hour = np.sin(2.0 * np.pi * hour_fraction / 24.0)
        cos_hour = np.cos(2.0 * np.pi * hour_fraction / 24.0)
        return pd.DataFrame(
            {"sin_hour": sin_hour, "cos_hour": cos_hour},
            index=timestamps.index,
        )

    def extract_features(
        self,
        df: pd.DataFrame,
        is_training: bool = False,
    ) -> pd.DataFrame:
        """Extract all engineered features from raw telemetry dataframe.
        
        Args:
            df: DataFrame containing at least RAW_TELEMETRY_COLUMNS and 'timestamp'.
                If 'service_id' is present, rolling stats are partitioned by service.
            is_training: If True, indicates batch training mode.
        """
        data = df.copy()
        if "timestamp" in data.columns:
            data = data.sort_values(by=["service_id", "timestamp"] if "service_id" in data.columns else "timestamp")
        
        feature_parts: List[pd.DataFrame] = []

        # 1. Base telemetry features
        base_df = data[RAW_TELEMETRY_COLUMNS].copy()
        feature_parts.append(base_df)

        # 2. Cyclical temporal features
        if "timestamp" in data.columns:
            time_features = self._compute_cyclical_time(data["timestamp"])
            feature_parts.append(time_features)
        else:
            # Default fallback for online synthetic single point
            feature_parts.append(pd.DataFrame({"sin_hour": [0.0] * len(data), "cos_hour": [1.0] * len(data)}, index=data.index))

        # 3. Rolling window statistics and Rate of Change (per service partition)
        rolling_dfs: List[pd.DataFrame] = []
        delta_dfs: List[pd.DataFrame] = []

        def _calc_partition_stats(partition: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
            p_roll: Dict[str, pd.Series] = {}
            p_delta: Dict[str, pd.Series] = {}

            # Rate of change: first difference
            for col in ROLLING_TARGET_COLUMNS:
                delta = partition[col].diff().fillna(0.0)
                p_delta[f"{col}_delta"] = delta

            # Rolling stats: mean & std over defined steps
            for window in self.rolling_windows:
                for col in ROLLING_TARGET_COLUMNS:
                    roll_mean = partition[col].rolling(window=window, min_periods=1).mean()
                    roll_std = partition[col].rolling(window=window, min_periods=1).std().fillna(0.0)
                    p_roll[f"{col}_roll_mean_{window}"] = roll_mean
                    p_roll[f"{col}_roll_std_{window}"] = roll_std

            return pd.DataFrame(p_roll, index=partition.index), pd.DataFrame(p_delta, index=partition.index)

        if "service_id" in data.columns and len(data["service_id"].unique()) > 1:
            for _, group in data.groupby("service_id", sort=False):
                r_df, d_df = _calc_partition_stats(group)
                rolling_dfs.append(r_df)
                delta_dfs.append(d_df)
            combined_roll = pd.concat(rolling_dfs).sort_index()
            combined_delta = pd.concat(delta_dfs).sort_index()
        else:
            combined_roll, combined_delta = _calc_partition_stats(data)

        feature_parts.append(combined_roll)
        feature_parts.append(combined_delta)

        # Assemble full unscaled feature matrix
        full_df = pd.concat(feature_parts, axis=1)
        full_df = full_df.fillna(0.0)

        return full_df

    def fit(self, X: pd.DataFrame, y: Optional[Any] = None) -> TelemetryFeaturePipeline:
        """Fit feature extractor and scaler strictly on the training partition."""
        features_df = self.extract_features(X, is_training=True)
        self.feature_names_ = list(features_df.columns)
        self.scaler.fit(features_df.values)
        self._is_fitted = True
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Extract features and transform with the fitted scaler."""
        if not self._is_fitted:
            raise RuntimeError("TelemetryFeaturePipeline is not fitted yet. Call fit() before transform().")
        features_df = self.extract_features(X, is_training=False)
        # Ensure column alignment
        features_df = features_df[self.feature_names_]
        return self.scaler.transform(features_df.values)

    def fit_transform(self, X: pd.DataFrame, y: Optional[Any] = None) -> np.ndarray:
        """Fit to training data, then transform."""
        return self.fit(X, y).transform(X)

    def extract_single_point(
        self,
        metric_dict: Dict[str, Any],
        recent_history: Optional[List[Dict[str, Any]]] = None,
    ) -> np.ndarray:
        """Feature extraction helper for online single-record inference.
        
        Args:
            metric_dict: Current incoming metric telemetry record.
            recent_history: Optional buffer of recent historical metrics for rolling context.
        """
        if recent_history and len(recent_history) > 0:
            all_records = list(recent_history) + [metric_dict]
            df = pd.DataFrame(all_records)
            scaled = self.transform(df)
            return scaled[-1:].copy()
        else:
            # Cold-start single point: fallback with zero deltas and current values as rolling mean
            df = pd.DataFrame([metric_dict])
            features_df = self.extract_features(df, is_training=False)
            features_df = features_df[self.feature_names_]
            return self.scaler.transform(features_df.values)
