"""Unit tests for sequence dataset construction, anti-leakage splitting, and collation."""

from datetime import datetime, timedelta, timezone
import pandas as pd
import pytest
import torch

from app.ml.deep_learning.data.sequence_dataset import (
    AntiLeakageSequenceSplitter,
    LogSequence,
    LogSequenceBuilder,
    PyTorchLogDataset,
    pad_sequence_collate,
)
from app.ml.deep_learning.preprocessing.log_tokenizer import (
    PAD_IDX,
    LogNormalizer,
    LogTemplateMiner,
    LogVocabulary,
)


@pytest.fixture
def sample_miner_and_vocab():
    normalizer = LogNormalizer()
    miner = LogTemplateMiner(normalizer=normalizer)
    raw_msgs = [
        "Normal operation trace id 100",
        "Warning: high CPU load 90%",
        "Error: DB pool timeout HikariPool-1",
        "Process terminated exit code 137",
    ]
    miner.fit(raw_msgs)

    vocab = LogVocabulary()
    vocab.build_from_tokens([miner.transform(raw_msgs)])
    vocab.freeze()
    return miner, vocab


def test_log_sequence_builder(sample_miner_and_vocab):
    miner, vocab = sample_miner_and_vocab
    builder = LogSequenceBuilder(miner=miner, vocab=vocab, window_size=5, stride=2, anomaly_threshold_ratio=0.20)

    now = datetime.now(timezone.utc)
    records = []
    # 12 normal logs, then 3 anomaly logs
    for i in range(15):
        records.append({
            "service_id": "auth-service",
            "timestamp": now + timedelta(seconds=i * 10),
            "message": "Normal operation trace id 100" if i < 12 else "Error: DB pool timeout HikariPool-1",
            "is_anomaly": 0 if i < 12 else 1,
        })
    df = pd.DataFrame(records)

    sequences = builder.build_sequences_from_dataframe(df)
    assert len(sequences) > 0

    # Early windows should be normal (0)
    assert sequences[0].label == 0
    # Later windows containing multiple anomaly logs should be anomalous (1)
    last_seq = sequences[-1]
    assert last_seq.label == 1
    assert last_seq.length == 5


def test_anti_leakage_splitter_guarantees_no_overlap():
    now = datetime.now(timezone.utc)
    records = []
    for i in range(100):
        records.append({
            "timestamp": now + timedelta(minutes=i * 5),
            "message": f"Log message sample {i}",
            "service_id": "api-gateway",
            "is_anomaly": 1 if 20 <= i <= 30 or 75 <= i <= 85 else 0,
        })
    df = pd.DataFrame(records)

    splitter = AntiLeakageSequenceSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df = splitter.split_by_chronological_windows(df)

    # 1. Total samples conserved
    assert len(train_df) + len(val_df) + len(test_df) == 100

    # 2. Strict chronological monotonicity: Train Max < Val Min <= Val Max < Test Min
    assert train_df["timestamp"].max() < val_df["timestamp"].min()
    assert val_df["timestamp"].max() < test_df["timestamp"].min()

    # 3. Disjoint indices
    train_indices = set(train_df.index)
    val_indices = set(val_df.index)
    test_indices = set(test_df.index)
    assert train_indices.isdisjoint(val_indices)
    assert val_indices.isdisjoint(test_indices)


def test_pytorch_dataset_and_pad_collate():
    seq1 = LogSequence(tokens=["E1", "E2"], token_ids=[4, 5], label=0, service_id="svc-1")
    seq2 = LogSequence(tokens=["E1", "E2", "E3", "E4"], token_ids=[4, 5, 6, 7], label=1, service_id="svc-2")

    dataset = PyTorchLogDataset([seq1, seq2])
    assert len(dataset) == 2
    assert dataset[0]["label"].item() == 0
    assert dataset[1]["label"].item() == 1

    # Collate batch with variable sequence lengths (2 and 4)
    batch = [dataset[0], dataset[1]]
    collated = pad_sequence_collate(batch)

    # Expected padded shape: [2, 4]
    input_ids = collated["input_ids"]
    assert input_ids.shape == (2, 4)
    # Check that shorter sequence was padded with PAD_IDX (0)
    assert input_ids[0, 2].item() == PAD_IDX
    assert input_ids[0, 3].item() == PAD_IDX
    assert collated["lengths"].tolist() == [2, 4]
    assert collated["labels"].tolist() == [0, 1]
