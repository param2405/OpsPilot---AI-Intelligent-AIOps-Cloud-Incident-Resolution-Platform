"""Unit tests for PyTorchTrainer, EarlyStopping, and checkpointing."""

import os
import tempfile
import pytest
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from app.ml.deep_learning.data.sequence_dataset import (
    LogSequence,
    PyTorchLogDataset,
    pad_sequence_collate,
)
from app.ml.deep_learning.models.sequence_model import LogSequenceLSTM
from app.ml.deep_learning.training.trainer import EarlyStopping, PyTorchTrainer


def test_early_stopping_logic():
    # Max mode (e.g. F1)
    es = EarlyStopping(patience=3, min_delta=0.01, mode="max")
    assert es.step(0.50, epoch=1) is True  # New best
    assert es.step(0.505, epoch=2) is False  # Not enough improvement (< 0.01)
    assert es.step(0.506, epoch=3) is False
    assert es.early_stop is False
    assert es.step(0.504, epoch=4) is False
    assert es.early_stop is True  # Patience of 3 reached

    # Min mode (e.g. Loss)
    es_min = EarlyStopping(patience=2, min_delta=0.01, mode="min")
    assert es_min.step(0.90, epoch=1) is True
    assert es_min.step(0.85, epoch=2) is True  # Improved
    assert es_min.counter == 0
    assert es_min.step(0.849, epoch=3) is False
    assert es_min.step(0.850, epoch=4) is False
    assert es_min.early_stop is True


def test_trainer_fit_and_checkpoint():
    vocab_size = 15
    model = LogSequenceLSTM(vocab_size=vocab_size, embedding_dim=16, hidden_dim=16, num_layers=1, num_classes=2)

    # Synthetic sequences
    sequences = [
        LogSequence(tokens=["E1", "E2"], token_ids=[4, 5], label=0, service_id="s1"),
        LogSequence(tokens=["E1", "E2"], token_ids=[4, 5], label=0, service_id="s1"),
        LogSequence(tokens=["E3", "E4"], token_ids=[6, 7], label=1, service_id="s2"),
        LogSequence(tokens=["E3", "E4"], token_ids=[6, 7], label=1, service_id="s2"),
    ] * 5  # 20 samples

    dataset = PyTorchLogDataset(sequences)
    train_loader = DataLoader(dataset, batch_size=4, shuffle=True, collate_fn=pad_sequence_collate)
    val_loader = DataLoader(dataset, batch_size=4, shuffle=False, collate_fn=pad_sequence_collate)

    with tempfile.TemporaryDirectory() as tmpdir:
        trainer = PyTorchTrainer(
            model=model,
            checkpoint_dir=tmpdir,
            early_stopping=EarlyStopping(patience=5, mode="min"),
        )

        summary = trainer.fit(
            train_loader=train_loader,
            val_loader=val_loader,
            epochs=3,
            model_name="test_lstm",
        )

        assert "train_loss" in summary["history"]
        assert len(summary["history"]["train_loss"]) == 3
        assert summary["total_epochs_trained"] == 3

        # Checkpoint should have been created
        ckpt_path = os.path.join(tmpdir, "test_lstm_best.pt")
        assert os.path.exists(ckpt_path)

        # Test loading checkpoint
        loaded = trainer.load_checkpoint(ckpt_path)
        assert "model_state_dict" in loaded
        assert "metrics" in loaded
