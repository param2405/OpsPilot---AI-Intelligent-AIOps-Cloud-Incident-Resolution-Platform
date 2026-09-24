"""Real-time inference engine for PyTorch log sequence anomaly detection and root trigger attribution."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn

from app.ml.deep_learning.models.sequence_model import (
    LogSequenceGRU,
    LogSequenceLSTM,
    create_sequence_model,
)
from app.ml.deep_learning.preprocessing.log_tokenizer import (
    PAD_IDX,
    LogNormalizer,
    LogTemplateMiner,
    LogVocabulary,
)

logger = logging.getLogger(__name__)


class LogSequenceInferenceEngine:
    """Production inference engine evaluating real-time operational log streams."""

    def __init__(
        self,
        model: Optional[nn.Module] = None,
        vocab: Optional[LogVocabulary] = None,
        miner: Optional[LogTemplateMiner] = None,
        normalizer: Optional[LogNormalizer] = None,
        device: Optional[torch.device] = None,
        checkpoint_path: Optional[str] = None,
    ) -> None:
        self.device = device or torch.device("cpu")
        self.normalizer = normalizer or LogNormalizer()
        self.miner = miner or LogTemplateMiner(normalizer=self.normalizer)
        self.vocab = vocab or LogVocabulary()
        self.model = model

        if checkpoint_path and os.path.exists(checkpoint_path):
            self.load_from_checkpoint(checkpoint_path)
        elif self.model is not None:
            self.model.to(self.device)
            self.model.eval()

    def load_from_checkpoint(self, checkpoint_path: str) -> None:
        """Load trained PyTorch weights and associated vocabulary."""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        model_state = checkpoint["model_state_dict"]
        extra = checkpoint.get("extra_data", {})

        # Reconstruct vocabulary if stored
        if "vocab" in extra:
            self.vocab = LogVocabulary.from_dict(extra["vocab"])
        if "miner" in extra:
            self.miner = LogTemplateMiner.from_dict(extra["miner"])

        arch = extra.get("architecture", "lstm")
        vocab_size = extra.get("vocab_size", len(self.vocab))
        embedding_dim = extra.get("embedding_dim", 64)
        hidden_dim = extra.get("hidden_dim", 64)
        num_layers = extra.get("num_layers", 2)
        num_classes = extra.get("num_classes", 2)
        bidirectional = extra.get("bidirectional", True)

        self.model = create_sequence_model(
            architecture=arch,
            vocab_size=vocab_size,
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            num_classes=num_classes,
            bidirectional=bidirectional,
        ).to(self.device)

        self.model.load_state_dict(model_state)
        self.model.eval()
        logger.info("Loaded LogSequenceInferenceEngine from %s (arch=%s, vocab=%d)", checkpoint_path, arch, vocab_size)

    def predict(
        self,
        messages: List[str],
        service_id: str = "unknown",
        threshold: float = 0.50,
    ) -> Dict[str, Any]:
        """Perform real-time sequence inference on a temporal list of raw log messages.
        
        Args:
            messages: List of raw operational log lines ordered chronologically.
            service_id: Microservice ID associated with the logs.
            threshold: Probability cutoff for classifying as anomalous.
        Returns:
            Dictionary with prediction, probabilities, attention attribution, and latency.
        """
        if self.model is None:
            raise RuntimeError("Cannot run inference: Model is not initialized or loaded.")

        start_time = time.perf_counter()

        if not messages:
            return {
                "service_id": service_id,
                "is_anomaly": False,
                "anomaly_probability": 0.0,
                "confidence": 1.0,
                "predicted_class": 0,
                "sequence_length": 0,
                "event_tokens": [],
                "top_trigger_event": None,
                "attention_weights": [],
                "latency_ms": 0.0,
            }

        # 1. Normalization and Event Mapping
        event_tokens = self.miner.transform(messages)

        # 2. Vocabulary integer encoding
        token_ids = self.vocab.encode(event_tokens)

        # 3. Form input tensor [1, SeqLen]
        input_tensor = torch.tensor([token_ids], dtype=torch.long, device=self.device)

        # 4. Model forward pass
        self.model.eval()
        with torch.no_grad():
            logits, attn_weights = self.model(input_tensor)
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
            attn = attn_weights.cpu().numpy()[0].tolist()

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        anomaly_prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
        is_anomaly = anomaly_prob >= threshold
        pred_class = int(np.argmax(probs))
        confidence = float(np.max(probs))

        # Identify top trigger event by maximum attention weight
        top_trigger_info = None
        if len(attn) > 0 and len(messages) == len(attn):
            max_idx = int(np.argmax(attn))
            top_trigger_info = {
                "index": max_idx,
                "log_message": messages[max_idx],
                "event_id": event_tokens[max_idx],
                "attention_weight": round(float(attn[max_idx]), 4),
            }

        return {
            "service_id": service_id,
            "is_anomaly": is_anomaly,
            "anomaly_probability": round(anomaly_prob, 4),
            "confidence": round(confidence, 4),
            "predicted_class": pred_class,
            "sequence_length": len(messages),
            "event_tokens": event_tokens,
            "top_trigger_event": top_trigger_info,
            "attention_weights": [round(w, 4) for w in attn],
            "latency_ms": elapsed_ms,
        }
