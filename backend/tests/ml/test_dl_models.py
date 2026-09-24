"""Unit tests for neural architectures (LSTM, GRU) and baseline sequence classifier."""

import pytest
import torch

from app.ml.deep_learning.data.sequence_dataset import LogSequence
from app.ml.deep_learning.models.baseline_classifier import LogEventCountBaseline
from app.ml.deep_learning.models.sequence_model import (
    LogSequenceGRU,
    LogSequenceLSTM,
    TemporalAttentionPooling,
    create_sequence_model,
)


def test_baseline_classifier_fit_and_predict():
    train_seqs = [
        LogSequence(tokens=["E1", "E2"], token_ids=[4, 5], label=0, service_id="s1"),
        LogSequence(tokens=["E1", "E2"], token_ids=[4, 5], label=0, service_id="s1"),
        LogSequence(tokens=["E3", "E4"], token_ids=[6, 7], label=1, service_id="s2"),
        LogSequence(tokens=["E3", "E4"], token_ids=[6, 7], label=1, service_id="s2"),
    ]

    baseline = LogEventCountBaseline(vocab_size=10, ngram_range=(1, 2))
    baseline.fit(train_seqs)
    assert baseline.is_fitted

    preds = baseline.predict(train_seqs)
    assert len(preds) == 4
    assert preds[0] == 0
    assert preds[2] == 1

    metrics = baseline.evaluate(train_seqs)
    assert metrics["accuracy"] == 1.0
    assert metrics["f1"] == 1.0


def test_temporal_attention_pooling():
    hidden_dim = 16
    batch_size = 2
    seq_len = 4

    pooling = TemporalAttentionPooling(hidden_dim=hidden_dim)
    hidden_states = torch.randn(batch_size, seq_len, hidden_dim)

    # Mask: sequence 0 has length 2, sequence 1 has length 4
    mask = torch.tensor([
        [True, True, False, False],
        [True, True, True, True],
    ])

    context, weights = pooling(hidden_states, mask=mask)

    assert context.shape == (batch_size, hidden_dim)
    assert weights.shape == (batch_size, seq_len)

    # Attention weights must sum to 1.0 per sequence
    assert torch.allclose(weights.sum(dim=-1), torch.ones(batch_size), atol=1e-5)

    # Padded steps in sequence 0 should receive 0 attention weight
    assert weights[0, 2].item() < 1e-4
    assert weights[0, 3].item() < 1e-4


def test_lstm_sequence_model_forward():
    vocab_size = 20
    batch_size = 4
    seq_len = 10
    num_classes = 2

    model = LogSequenceLSTM(
        vocab_size=vocab_size,
        embedding_dim=16,
        hidden_dim=32,
        num_layers=2,
        num_classes=num_classes,
        bidirectional=True,
    )

    inputs = torch.randint(0, vocab_size, (batch_size, seq_len))
    logits, attn_weights = model(inputs)

    assert logits.shape == (batch_size, num_classes)
    assert attn_weights.shape == (batch_size, seq_len)

    probs = model.predict_proba(inputs)
    assert probs.shape == (batch_size, num_classes)
    assert torch.allclose(probs.sum(dim=-1), torch.ones(batch_size), atol=1e-5)


def test_gru_sequence_model_forward():
    vocab_size = 20
    batch_size = 4
    seq_len = 8
    num_classes = 2

    model = LogSequenceGRU(
        vocab_size=vocab_size,
        embedding_dim=16,
        hidden_dim=32,
        num_layers=2,
        num_classes=num_classes,
        bidirectional=True,
    )

    inputs = torch.randint(0, vocab_size, (batch_size, seq_len))
    logits, attn_weights = model(inputs)

    assert logits.shape == (batch_size, num_classes)
    assert attn_weights.shape == (batch_size, seq_len)


def test_create_sequence_model_factory():
    lstm = create_sequence_model("lstm", vocab_size=15)
    assert isinstance(lstm, LogSequenceLSTM)

    gru = create_sequence_model("gru", vocab_size=15)
    assert isinstance(gru, LogSequenceGRU)

    with pytest.raises(ValueError):
        create_sequence_model("transformer", vocab_size=15)
