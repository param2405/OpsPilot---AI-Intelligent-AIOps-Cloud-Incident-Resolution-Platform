"""PyTorch recurrent sequence architectures (LSTM and GRU) for log sequence modeling."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Union
import torch
import torch.nn as nn
import torch.nn.functional as F

from app.ml.deep_learning.preprocessing.log_tokenizer import PAD_IDX

logger = logging.getLogger(__name__)


class TemporalAttentionPooling(nn.Module):
    """Self-attention pooling mechanism over recurrent sequence hidden states.
    
    Computes a learned normalized scalar importance weight alpha_t for each step in the log sequence.
    This produces:
      1. A rich, context-weighted summary vector c = sum(alpha_t * h_t).
      2. Interpretable attention weights pinpointing which specific log event triggered the anomaly.
    """

    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.projection = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1, bias=False),
        )

    def forward(
        self,
        hidden_states: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            hidden_states: [Batch, SeqLen, HiddenDim]
            mask: [Batch, SeqLen] boolean mask (True for valid tokens, False for padded)
        Returns:
            pooled_context: [Batch, HiddenDim]
            attention_weights: [Batch, SeqLen]
        """
        # Score each hidden state: [Batch, SeqLen, 1]
        scores = self.projection(hidden_states).squeeze(-1)  # [Batch, SeqLen]

        if mask is not None:
            # Mask out padding tokens with a large negative value before softmax
            scores = scores.masked_fill(~mask, -1e9)

        weights = F.softmax(scores, dim=-1)  # [Batch, SeqLen]

        # In case all tokens were masked (safety guard)
        weights = torch.nan_to_num(weights, nan=0.0)

        # Context vector: sum(weights * hidden_states) -> [Batch, HiddenDim]
        context = torch.bmm(weights.unsqueeze(1), hidden_states).squeeze(1)
        return context, weights


class LogSequenceLSTM(nn.Module):
    """Bidirectional LSTM sequence classifier for operational log sequences.
    
    Architecture:
      Embedding Layer (vocab_size -> embedding_dim)
      -> Dropout
      -> Multi-layer Bidirectional LSTM
      -> Temporal Self-Attention Pooling
      -> Classification MLP (Linear -> LayerNorm -> ReLU -> Dropout -> Linear -> Logits)
    """

    def __init__(
        self,
        vocab_size: int,
        embedding_dim: int = 64,
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_classes: int = 2,
        bidirectional: bool = True,
        dropout: float = 0.2,
        padding_idx: int = PAD_IDX,
    ) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_classes = num_classes
        self.bidirectional = bidirectional
        self.num_directions = 2 if bidirectional else 1
        self.padding_idx = padding_idx

        # 1. Token Embedding
        self.embedding = nn.Embedding(
            num_embeddings=vocab_size,
            embedding_dim=embedding_dim,
            padding_idx=padding_idx,
        )
        self.embed_dropout = nn.Dropout(p=dropout)

        # 2. Recurrent LSTM
        self.lstm = nn.LSTM(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        # 3. Attention Pooling
        recurrent_output_dim = hidden_dim * self.num_directions
        self.attention = TemporalAttentionPooling(hidden_dim=recurrent_output_dim)

        # 4. Dense Classification Head
        self.classifier = nn.Sequential(
            nn.Linear(recurrent_output_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(p=dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        lengths: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass.
        
        Args:
            input_ids: [Batch, SeqLen] tensor of token IDs
            lengths: Optional [Batch] sequence lengths
        Returns:
            logits: [Batch, NumClasses] unnormalized logit predictions
            attention_weights: [Batch, SeqLen] importance weights per event step
        """
        # Create padding mask [Batch, SeqLen] where True = non-pad
        mask = input_ids != self.padding_idx

        # 1. Embed tokens: [Batch, SeqLen, EmbeddingDim]
        embedded = self.embed_dropout(self.embedding(input_ids))

        # 2. LSTM recurrent pass: [Batch, SeqLen, HiddenDim * NumDirections]
        lstm_out, _ = self.lstm(embedded)

        # 3. Attention pooling over valid sequence steps: [Batch, RecurrentDim]
        context, attn_weights = self.attention(lstm_out, mask=mask)

        # 4. Classification logits: [Batch, NumClasses]
        logits = self.classifier(context)

        return logits, attn_weights

    def predict_proba(self, input_ids: torch.Tensor) -> torch.Tensor:
        """Compute softmax probabilities in inference mode."""
        self.eval()
        with torch.no_grad():
            logits, _ = self.forward(input_ids)
            return F.softmax(logits, dim=-1)


class LogSequenceGRU(nn.Module):
    """Gated Recurrent Unit (GRU) sequence classifier for operational log sequences.
    
    A computationally lighter alternative to LSTM with fewer gating parameters (update & reset gates)
    offering faster inference times and reduced memory footprint.
    """

    def __init__(
        self,
        vocab_size: int,
        embedding_dim: int = 64,
        hidden_dim: int = 64,
        num_layers: int = 2,
        num_classes: int = 2,
        bidirectional: bool = True,
        dropout: float = 0.2,
        padding_idx: int = PAD_IDX,
    ) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_classes = num_classes
        self.bidirectional = bidirectional
        self.num_directions = 2 if bidirectional else 1
        self.padding_idx = padding_idx

        self.embedding = nn.Embedding(
            num_embeddings=vocab_size,
            embedding_dim=embedding_dim,
            padding_idx=padding_idx,
        )
        self.embed_dropout = nn.Dropout(p=dropout)

        self.gru = nn.GRU(
            input_size=embedding_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=bidirectional,
            dropout=dropout if num_layers > 1 else 0.0,
        )

        recurrent_output_dim = hidden_dim * self.num_directions
        self.attention = TemporalAttentionPooling(hidden_dim=recurrent_output_dim)

        self.classifier = nn.Sequential(
            nn.Linear(recurrent_output_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(p=dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        lengths: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        mask = input_ids != self.padding_idx
        embedded = self.embed_dropout(self.embedding(input_ids))
        gru_out, _ = self.gru(embedded)
        context, attn_weights = self.attention(gru_out, mask=mask)
        logits = self.classifier(context)
        return logits, attn_weights

    def predict_proba(self, input_ids: torch.Tensor) -> torch.Tensor:
        self.eval()
        with torch.no_grad():
            logits, _ = self.forward(input_ids)
            return F.softmax(logits, dim=-1)


def create_sequence_model(
    architecture: str = "lstm",
    vocab_size: int = 100,
    embedding_dim: int = 64,
    hidden_dim: int = 64,
    num_layers: int = 2,
    num_classes: int = 2,
    bidirectional: bool = True,
    dropout: float = 0.2,
) -> nn.Module:
    """Factory function for instantiating sequence models."""
    arch = architecture.lower().strip()
    if arch == "lstm":
        return LogSequenceLSTM(
            vocab_size=vocab_size,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_classes=num_classes,
            bidirectional=bidirectional,
            dropout=dropout,
        )
    elif arch == "gru":
        return LogSequenceGRU(
            vocab_size=vocab_size,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_classes=num_classes,
            bidirectional=bidirectional,
            dropout=dropout,
        )
    else:
        raise ValueError(f"Unknown architecture '{architecture}'. Supported: 'lstm', 'gru'")
