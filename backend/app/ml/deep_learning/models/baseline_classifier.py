"""Non-neural Bag-of-Events baseline classifier for log sequence analysis."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from app.ml.deep_learning.data.sequence_dataset import LogSequence

logger = logging.getLogger(__name__)


class LogEventCountBaseline:
    """Non-neural benchmark baseline using Bag-of-Events (BoE) / N-gram counts + Logistic Regression.
    
    Why this baseline is crucial:
    Standard tabular models represent a sequence purely as a frequency histogram of event types,
    discarding time ordering:
      Seq A: [HealthOK -> HighCPU -> ServiceDead] (orderly progression into crash)
      Seq B: [ServiceDead -> HighCPU -> HealthOK] (recovery into health)
    Bag-of-events treats Seq A and Seq B as completely identical.
    Comparing this baseline with recurrent neural models mathematically proves whether
    sequential/temporal ordering adds predictive signal.
    """

    def __init__(
        self,
        vocab_size: int = 100,
        ngram_range: Tuple[int, int] = (1, 2),
        C: float = 1.0,
        random_state: int = 42,
    ) -> None:
        self.vocab_size = vocab_size
        self.ngram_range = ngram_range
        self.C = C
        self.random_state = random_state
        self.classifier = LogisticRegression(
            C=C,
            class_weight="balanced",
            max_iter=1000,
            random_state=random_state,
        )
        self.is_fitted = False
        self._bigram_to_idx: Dict[Tuple[int, int], int] = {}

    def _extract_features(self, sequences: List[LogSequence], fit_bigrams: bool = False) -> np.ndarray:
        """Convert sequences into unigram event frequency counts and optional bigram counts."""
        n_samples = len(sequences)
        # Unigrams: counts of each token_id in vocabulary
        unigram_matrix = np.zeros((n_samples, self.vocab_size), dtype=np.float32)

        for i, seq in enumerate(sequences):
            for token_id in seq.token_ids:
                if 0 <= token_id < self.vocab_size:
                    unigram_matrix[i, token_id] += 1.0

        if self.ngram_range[1] <= 1:
            return unigram_matrix

        # Extract bigrams
        if fit_bigrams:
            self._bigram_to_idx.clear()
            for seq in sequences:
                ids = seq.token_ids
                for j in range(len(ids) - 1):
                    pair = (ids[j], ids[j + 1])
                    if pair not in self._bigram_to_idx:
                        self._bigram_to_idx[pair] = len(self._bigram_to_idx)

        bigram_matrix = np.zeros((n_samples, len(self._bigram_to_idx)), dtype=np.float32)
        if len(self._bigram_to_idx) > 0:
            for i, seq in enumerate(sequences):
                ids = seq.token_ids
                for j in range(len(ids) - 1):
                    pair = (ids[j], ids[j + 1])
                    if pair in self._bigram_to_idx:
                        bigram_matrix[i, self._bigram_to_idx[pair]] += 1.0

        return np.hstack([unigram_matrix, bigram_matrix])

    def fit(self, sequences: List[LogSequence]) -> "LogEventCountBaseline":
        """Fit the baseline classifier on training sequences."""
        if not sequences:
            raise ValueError("Cannot fit baseline on empty sequences list")

        X = self._extract_features(sequences, fit_bigrams=True)
        y = np.array([seq.label for seq in sequences], dtype=np.int64)

        self.classifier.fit(X, y)
        self.is_fitted = True
        logger.info(
            "Fitted LogEventCountBaseline (samples=%d, features=%d, classes=%s)",
            len(sequences),
            X.shape[1],
            self.classifier.classes_.tolist(),
        )
        return self

    def predict(self, sequences: List[LogSequence]) -> np.ndarray:
        """Predict binary anomaly labels (0 or 1) for sequences."""
        if not self.is_fitted:
            raise RuntimeError("Baseline model must be fitted before predict()")
        X = self._extract_features(sequences, fit_bigrams=False)
        return self.classifier.predict(X)

    def predict_proba(self, sequences: List[LogSequence]) -> np.ndarray:
        """Predict anomaly probabilities for sequences."""
        if not self.is_fitted:
            raise RuntimeError("Baseline model must be fitted before predict_proba()")
        X = self._extract_features(sequences, fit_bigrams=False)
        return self.classifier.predict_proba(X)

    def evaluate(self, sequences: List[LogSequence]) -> Dict[str, Any]:
        """Compute evaluation metrics on held-out test sequences."""
        if not sequences:
            return {}

        y_true = np.array([seq.label for seq in sequences], dtype=np.int64)
        y_pred = self.predict(sequences)
        y_proba = self.predict_proba(sequences)

        acc = float(accuracy_score(y_true, y_pred))
        prec = float(precision_score(y_true, y_pred, zero_division=0))
        rec = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))

        # Handle binary or multiclass ROC-AUC
        roc_auc = 0.0
        if len(np.unique(y_true)) > 1:
            try:
                if y_proba.shape[1] == 2:
                    roc_auc = float(roc_auc_score(y_true, y_proba[:, 1]))
                else:
                    roc_auc = float(roc_auc_score(y_true, y_proba, multi_class="ovr"))
            except Exception:
                roc_auc = 0.0

        cm = confusion_matrix(y_true, y_pred).tolist()

        return {
            "model_type": "non_neural_baseline",
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "confusion_matrix": cm,
            "sample_count": len(sequences),
        }
