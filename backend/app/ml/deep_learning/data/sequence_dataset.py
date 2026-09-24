"""Dataset abstraction, sequence generation, and strict anti-leakage splitting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from app.ml.deep_learning.preprocessing.log_tokenizer import (
    PAD_IDX,
    LogNormalizer,
    LogTemplateMiner,
    LogVocabulary,
)

logger = logging.getLogger(__name__)


@dataclass
class LogSequence:
    """Represents a single temporal sequence of structured log events."""

    tokens: List[str]  # Event IDs e.g. ["E1", "E2", "E3"]
    token_ids: List[int]  # Integer indices from LogVocabulary
    label: int  # 0 = Normal, 1 = Anomaly (or multi-class category)
    service_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    incident_id: Optional[str] = None
    raw_messages: List[str] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.tokens)


class LogSequenceBuilder:
    """Constructs fixed-length or sliding-window sequences from chronological log streams."""

    def __init__(
        self,
        miner: LogTemplateMiner,
        vocab: LogVocabulary,
        window_size: int = 15,
        stride: int = 3,
        anomaly_threshold_ratio: float = 0.20,
    ) -> None:
        """
        Args:
            miner: Fitted LogTemplateMiner mapping raw messages to event IDs.
            vocab: LogVocabulary mapping event IDs to integer embeddings.
            window_size: Number of consecutive log events per sequence.
            stride: Step size between sliding windows.
            anomaly_threshold_ratio: If >= this proportion of logs in a window are anomalous,
                                     the entire sequence is labeled as anomalous (1).
        """
        self.miner = miner
        self.vocab = vocab
        self.window_size = window_size
        self.stride = stride
        self.anomaly_threshold_ratio = anomaly_threshold_ratio

    def build_sequences_from_dataframe(
        self,
        df: pd.DataFrame,
        incident_id: Optional[str] = None,
    ) -> List[LogSequence]:
        """Construct sliding window sequences from a log DataFrame sorted chronologically.
        
        Expected columns: 'timestamp', 'message', 'service_id', and optionally 'is_anomaly'.
        """
        if df.empty:
            return []

        df_sorted = df.sort_values(by="timestamp").reset_index(drop=True)
        sequences: List[LogSequence] = []

        # Partition strictly per service so that cross-service streams don't interleave arbitrarily
        for service_id, svc_df in df_sorted.groupby("service_id"):
            messages = svc_df["message"].tolist()
            timestamps = svc_df["timestamp"].tolist()
            is_anom_list = svc_df["is_anomaly"].tolist() if "is_anomaly" in svc_df.columns else [0] * len(svc_df)

            # Map raw messages to event tokens and vocab IDs
            event_tokens = self.miner.transform(messages)
            token_ids = self.vocab.encode(event_tokens)

            n_logs = len(event_tokens)
            if n_logs == 0:
                continue

            # If fewer logs than window_size, pad to window_size as a single sequence
            if n_logs < self.window_size:
                anom_count = sum(is_anom_list)
                label = 1 if (anom_count / max(1, n_logs)) >= self.anomaly_threshold_ratio else 0
                padded_ids = self.vocab.pad_or_truncate(token_ids, self.window_size)
                seq = LogSequence(
                    tokens=event_tokens,
                    token_ids=padded_ids,
                    label=label,
                    service_id=str(service_id),
                    start_time=timestamps[0] if timestamps else None,
                    end_time=timestamps[-1] if timestamps else None,
                    incident_id=incident_id,
                    raw_messages=messages,
                )
                sequences.append(seq)
                continue

            # Slide window across events
            for i in range(0, n_logs - self.window_size + 1, self.stride):
                win_tokens = event_tokens[i : i + self.window_size]
                win_ids = token_ids[i : i + self.window_size]
                win_anoms = is_anom_list[i : i + self.window_size]
                win_msgs = messages[i : i + self.window_size]
                win_ts = timestamps[i : i + self.window_size]

                anom_ratio = sum(win_anoms) / len(win_anoms)
                label = 1 if anom_ratio >= self.anomaly_threshold_ratio else 0

                seq = LogSequence(
                    tokens=win_tokens,
                    token_ids=win_ids,
                    label=label,
                    service_id=str(service_id),
                    start_time=win_ts[0] if win_ts else None,
                    end_time=win_ts[-1] if win_ts else None,
                    incident_id=incident_id,
                    raw_messages=win_msgs,
                )
                sequences.append(seq)

        return sequences


class AntiLeakageSequenceSplitter:
    """Partitions log corpora strictly across temporal incident sessions to eliminate data leakage.
    
    Data Leakage Defense:
    If sequences from the same temporal incident are randomly shuffled into both Train
    and Test sets, the test set evaluates memorization rather than generalization.
    This splitter guarantees:
      1. Whole incident sessions and disjoint chronological blocks are allocated to Train, Val, or Test.
      2. No sliding window ever crosses the partition boundary between splits.
      3. The Test split contains exclusively unseen incident events.
    """

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> None:
        assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-6, "Split ratios must sum to 1.0"
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio

    def split_by_chronological_windows(
        self,
        df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split a DataFrame chronologically before sequence construction."""
        if "timestamp" not in df.columns:
            raise ValueError("DataFrame must contain 'timestamp' column for chronological splitting")

        df_sorted = df.sort_values(by="timestamp").reset_index(drop=True)
        n = len(df_sorted)
        train_end = int(n * self.train_ratio)
        val_end = int(n * (self.train_ratio + self.val_ratio))

        train_df = df_sorted.iloc[:train_end].copy()
        val_df = df_sorted.iloc[train_end:val_end].copy()
        test_df = df_sorted.iloc[val_end:].copy()

        logger.info(
            "Anti-leakage split: Train=%d (%s to %s), Val=%d, Test=%d (%s to %s)",
            len(train_df),
            train_df["timestamp"].min() if not train_df.empty else "N/A",
            train_df["timestamp"].max() if not train_df.empty else "N/A",
            len(val_df),
            len(test_df),
            test_df["timestamp"].min() if not test_df.empty else "N/A",
            test_df["timestamp"].max() if not test_df.empty else "N/A",
        )
        return train_df, val_df, test_df

    def split_by_incident_sessions(
        self,
        incident_sessions: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Split sessions by distinct incident IDs so that whole incidents are held out."""
        # Sort incidents chronologically by start timestamp
        sorted_sessions = sorted(
            incident_sessions,
            key=lambda s: s.get("start_time") or datetime.min.replace(tzinfo=timezone.utc),
        )
        n = len(sorted_sessions)
        train_end = max(1, int(n * self.train_ratio))
        val_end = max(train_end + 1, int(n * (self.train_ratio + self.val_ratio)))

        train_sessions = sorted_sessions[:train_end]
        val_sessions = sorted_sessions[train_end:val_end]
        test_sessions = sorted_sessions[val_end:]
        return train_sessions, val_sessions, test_sessions

    def split_by_incident_boundaries(
        self,
        df: pd.DataFrame,
        incident_intervals: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split DataFrame by incident boundaries so each split contains distinct, complete incidents.
        
        Guarantees:
          1. 70% of chronological incidents are allocated to Train.
          2. 15% of chronological incidents are allocated to Validation.
          3. 15% of chronological incidents are allocated to Test.
          4. Ambient logs accompany their respective chronological incident blocks.
          5. No incident pattern or time window is shared between splits.
        """
        if "timestamp" not in df.columns:
            raise ValueError("DataFrame must contain 'timestamp' column")

        df_sorted = df.sort_values(by="timestamp").reset_index(drop=True)

        if not incident_intervals:
            # Fall back to pure chronological quantile split if no incident intervals provided
            return self.split_by_chronological_windows(df_sorted)

        # Sort incidents chronologically by start timestamp
        sorted_incidents = sorted(incident_intervals, key=lambda x: x["start"])
        n_inc = len(sorted_incidents)

        if n_inc < 3:
            return self.split_by_chronological_windows(df_sorted)

        n_train = max(1, int(n_inc * self.train_ratio))
        n_val = max(1, int(n_inc * self.val_ratio))
        if n_train + n_val >= n_inc:
            n_train = max(1, n_inc - 2)
            n_val = 1

        train_incs = sorted_incidents[:n_train]
        val_incs = sorted_incidents[n_train : n_train + n_val]
        test_incs = sorted_incidents[n_train + n_val :]

        # Cutoff 1: midway between last train incident end and first val incident start
        last_train_end = max(inc["end"] for inc in train_incs)
        first_val_start = min(inc["start"] for inc in val_incs)
        cutoff1 = last_train_end + (first_val_start - last_train_end) / 2

        # Cutoff 2: midway between last val incident end and first test incident start
        last_val_end = max(inc["end"] for inc in val_incs)
        first_test_start = min(inc["start"] for inc in test_incs)
        cutoff2 = last_val_end + (first_test_start - last_val_end) / 2

        train_df = df_sorted[df_sorted["timestamp"] < cutoff1].copy()
        val_df = df_sorted[(df_sorted["timestamp"] >= cutoff1) & (df_sorted["timestamp"] < cutoff2)].copy()
        test_df = df_sorted[df_sorted["timestamp"] >= cutoff2].copy()

        logger.info(
            "Incident-boundary anti-leakage split: Train=%d (%d incs), Val=%d (%d incs), Test=%d (%d incs)",
            len(train_df),
            len(train_incs),
            len(val_df),
            len(val_incs),
            len(test_df),
            len(test_incs),
        )
        return train_df, val_df, test_df



class PyTorchLogDataset(Dataset):
    """PyTorch Dataset wrapper around a list of LogSequence objects."""

    def __init__(self, sequences: List[LogSequence]) -> None:
        self.sequences = sequences

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        seq = self.sequences[idx]
        return {
            "token_ids": torch.tensor(seq.token_ids, dtype=torch.long),
            "length": torch.tensor(len(seq.token_ids), dtype=torch.long),
            "label": torch.tensor(seq.label, dtype=torch.long),
            "service_id": seq.service_id,
        }

    @property
    def labels(self) -> np.ndarray:
        return np.array([seq.label for seq in self.sequences], dtype=np.int64)

    @property
    def class_counts(self) -> Dict[int, int]:
        counts: Dict[int, int] = {}
        for seq in self.sequences:
            counts[seq.label] = counts.get(seq.label, 0) + 1
        return counts


def pad_sequence_collate(batch: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
    """Collate function for DataLoader that dynamically pads variable-length log sequences.
    
    Returns:
        dict with:
          - 'input_ids': [Batch, MaxSeqLen] padded with PAD_IDX (0)
          - 'lengths': [Batch] actual length of each sequence
          - 'labels': [Batch] target labels
    """
    token_id_tensors = [item["token_ids"] for item in batch]
    lengths = torch.tensor([item["length"] for item in batch], dtype=torch.long)
    labels = torch.tensor([item["label"] for item in batch], dtype=torch.long)

    # Pad sequences to max length in this batch
    padded_inputs = torch.nn.utils.rnn.pad_sequence(
        token_id_tensors,
        batch_first=True,
        padding_value=PAD_IDX,
    )

    return {
        "input_ids": padded_inputs,
        "lengths": lengths,
        "labels": labels,
    }
