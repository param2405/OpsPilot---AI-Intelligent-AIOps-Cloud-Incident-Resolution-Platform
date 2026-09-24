"""Safe read-only mathematical statistics calculation tool for telemetry series analysis."""

from __future__ import annotations

import logging
from typing import List, Optional
import numpy as np

from app.schemas.agent import CalculateStatisticsOutput

logger = logging.getLogger(__name__)


def calculate_statistics(
    data: List[float],
    metric_name: str = "metric",
) -> CalculateStatisticsOutput:
    """Compute summary statistics, percentiles, and anomaly detection flags on numerical data series.
    
    Safe Boundaries:
      - Pure computational function without side effects.
      - Input size constrained to 10,000 points.
      - Handles degenerate / single-value lists gracefully.
    """
    if not data:
        return CalculateStatisticsOutput(
            metric_name=metric_name,
            count=0,
            mean=0.0,
            std_dev=0.0,
            min=0.0,
            max=0.0,
            median=0.0,
            p95=0.0,
            p99=0.0,
            anomaly_detected=False,
            status="success",
        )

    # Cap input to safe boundaries
    safe_data = data[:10000]
    arr = np.array(safe_data, dtype=np.float64)

    count = int(len(arr))
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    min_val = float(np.min(arr))
    max_val = float(np.max(arr))
    med_val = float(np.median(arr))
    p95_val = float(np.percentile(arr, 95))
    p99_val = float(np.percentile(arr, 99))

    # Anomaly detection: 2.0-sigma threshold or IQR outlier rule
    anomaly = False
    if count >= 3 and std_val > 0:
        z_scores = np.abs((arr - mean_val) / std_val)
        q75, q25 = np.percentile(arr, [75, 25])
        iqr = q75 - q25
        if np.any(z_scores >= 2.0) or (iqr > 0 and np.any(arr > q75 + 1.5 * iqr)):
            anomaly = True
        elif max_val > (med_val * 2.5) and max_val > 10.0:
            anomaly = True
    elif max_val > (mean_val * 2.0) and max_val > 10.0:
        anomaly = True

    return CalculateStatisticsOutput(
        metric_name=metric_name,
        count=count,
        mean=round(mean_val, 4),
        std_dev=round(std_val, 4),
        min=round(min_val, 4),
        max=round(max_val, 4),
        median=round(med_val, 4),
        p95=round(p95_val, 4),
        p99=round(p99_val, 4),
        anomaly_detected=anomaly,
        status="success",
    )
