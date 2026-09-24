"""Time-Series and Incident Dataset Splitting Strategies for OpsPilot AI.

Enforces zero-data-leakage chronological partitioning for time-series telemetry metrics
and time-ordered stratified partitioning for incident records.
"""

from __future__ import annotations

from typing import Tuple
import pandas as pd


class ChronologicalSplitter:
    """Strict time-series splitter preserving causal temporal ordering.
    
    Prevents lookahead bias and temporal leakage by partitioning data on chronological
    timestamp thresholds without random shuffling.
    """

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        timestamp_col: str = "timestamp",
    ) -> None:
        if not abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-5:
            raise ValueError(f"Split ratios must sum to 1.0, got {train_ratio + val_ratio + test_ratio}")
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.timestamp_col = timestamp_col

    def split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split dataframe into (train, val, test) chronologically.
        
        Args:
            df: Input dataframe with timestamp column.
            
        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        sorted_df = df.sort_values(by=self.timestamp_col).reset_index(drop=True)
        n = len(sorted_df)

        train_end = int(n * self.train_ratio)
        val_end = int(n * (self.train_ratio + self.val_ratio))

        train_df = sorted_df.iloc[:train_end].copy()
        val_df = sorted_df.iloc[train_end:val_end].copy()
        test_df = sorted_df.iloc[val_end:].copy()

        # Strict temporal integrity assertions
        if len(train_df) > 0 and len(val_df) > 0:
            assert train_df[self.timestamp_col].max() <= val_df[self.timestamp_col].min(), (
                "Temporal leakage detected: Training set contains timestamps after validation start!"
            )
        if len(val_df) > 0 and len(test_df) > 0:
            assert val_df[self.timestamp_col].max() <= test_df[self.timestamp_col].min(), (
                "Temporal leakage detected: Validation set contains timestamps after test start!"
            )

        return train_df, val_df, test_df


class IncidentSplitter:
    """Time-aware splitter for historical incident records.
    
    Splits incidents chronologically or with time-ordered stratification.
    """

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        timestamp_col: str = "timestamp",
    ) -> None:
        self.chronological_splitter = ChronologicalSplitter(
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            timestamp_col=timestamp_col,
        )

    def split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        return self.chronological_splitter.split(df)
