"""Unit tests for preprocessing, chronological splitting, and corpus generation."""

from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest

from app.ml.data.corpus_generator import CATEGORIES, HistoricalIncidentCorpusGenerator, SEVERITIES
from app.ml.data.splitter import ChronologicalSplitter


def test_chronological_splitter_zero_leakage() -> None:
    now = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    records = [
        {"id": i, "timestamp": now + timedelta(minutes=10 * i), "val": float(i)}
        for i in range(100)
    ]
    df = pd.DataFrame(records)

    splitter = ChronologicalSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df = splitter.split(df)

    assert len(train_df) == 70
    assert len(val_df) == 15
    assert len(test_df) == 15

    # Assert strict time progression (zero future leakage)
    assert train_df["timestamp"].max() <= val_df["timestamp"].min()
    assert val_df["timestamp"].max() <= test_df["timestamp"].min()


def test_corpus_generator_distribution_and_reproducibility() -> None:
    gen1 = HistoricalIncidentCorpusGenerator(seed=42)
    df1 = gen1.generate_corpus(n_samples=120)

    gen2 = HistoricalIncidentCorpusGenerator(seed=42)
    df2 = gen2.generate_corpus(n_samples=120)

    # Deterministic equality
    pd.testing.assert_frame_equal(df1, df2)

    # Check categories and severities
    assert set(df1["category"].unique()) == set(CATEGORIES)
    assert set(df1["severity"].unique()) == set(SEVERITIES)

    # Check valid telemetry ranges
    assert (df1["cpu_usage"] >= 0.0).all() and (df1["cpu_usage"] <= 100.0).all()
    assert (df1["memory_usage"] >= 0.0).all() and (df1["memory_usage"] <= 100.0).all()
    assert (df1["error_rate"] >= 0.0).all() and (df1["error_rate"] <= 1.0).all()
