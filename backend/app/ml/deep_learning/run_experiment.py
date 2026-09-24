"""Production experiment runner comparing non-neural baseline vs PyTorch LSTM vs GRU sequence models."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.incident import Incident
from app.ml.data.collector import ObservabilityDataCollector
from app.ml.deep_learning.data.sequence_dataset import (
    AntiLeakageSequenceSplitter,
    LogSequence,
    LogSequenceBuilder,
    PyTorchLogDataset,
    pad_sequence_collate,
)
from app.ml.deep_learning.models.baseline_classifier import LogEventCountBaseline
from app.ml.deep_learning.models.sequence_model import (
    LogSequenceGRU,
    LogSequenceLSTM,
    create_sequence_model,
)
from app.ml.deep_learning.preprocessing.log_tokenizer import (
    LogNormalizer,
    LogTemplateMiner,
    LogVocabulary,
)
from app.ml.deep_learning.training.trainer import EarlyStopping, PyTorchTrainer
from app.ml.tracking.mlflow_manager import MLflowTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dl_experiment")


def run_pipeline(
    model_choice: str = "all",
    epochs: int = 12,
    batch_size: int = 32,
    window_size: int = 15,
    stride: int = 3,
    lr: float = 1e-3,
    hidden_dim: int = 64,
    embedding_dim: int = 64,
    track_mlflow: bool = True,
    seed: int = 42,
    output_dir: str = "ml_models/log_sequence",
) -> Dict[str, Any]:
    """Execute complete deep learning log analysis experiment."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=================================================================")
    logger.info("  OpsPilot AI — Deep Learning Log Sequence Experiment (Phase 4)")
    logger.info("=================================================================")

    # 1. Load operational logs from database
    collector = ObservabilityDataCollector()
    df = collector.load_logs_with_ground_truth()
    logger.info("Loaded %d operational log entries (Anomalous logs=%d)", len(df), int(df["is_anomaly"].sum()))

    # 2. Anti-Leakage Partitioning by Incident Boundaries
    # Whole incidents and their operational time intervals are allocated exclusively
    # to either Train (70%), Val (15%), or Test (15%) before constructing sliding windows.
    db = SessionLocal()
    try:
        incident_stmt = select(Incident)
        inc_records = db.scalars(incident_stmt).all()
        incident_intervals = [
            {
                "id": inc.id,
                "service_id": inc.service_id,
                "start": collector._to_utc(inc.started_at),
                "end": collector._to_utc(inc.resolved_at) or collector._to_utc(inc.started_at),
            }
            for inc in inc_records
        ]
    finally:
        db.close()

    splitter = AntiLeakageSequenceSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df = splitter.split_by_incident_boundaries(df, incident_intervals)

    # 3. Fit Template Miner and Vocabulary strictly on Train split (to avoid vocabulary leakage!)
    normalizer = LogNormalizer()
    miner = LogTemplateMiner(normalizer=normalizer)
    miner.fit(train_df["message"].tolist())
    logger.info("Discovered %d unique log templates on train split.", miner.num_templates)

    # Build vocabulary strictly from train event tokens
    train_event_tokens = [miner.transform(train_df["message"].tolist())]
    vocab = LogVocabulary()
    vocab.build_from_tokens(train_event_tokens, min_freq=1)
    vocab.freeze()
    logger.info("Built LogVocabulary with %d tokens (including special tokens).", len(vocab))

    # Save vocabulary and miner
    vocab.save(os.path.join(output_dir, "vocab.json"))
    with open(os.path.join(output_dir, "miner.json"), "w", encoding="utf-8") as f:
        json.dump(miner.to_dict(), f, indent=2)

    # 4. Construct sliding-window sequences independently within each split
    builder = LogSequenceBuilder(
        miner=miner,
        vocab=vocab,
        window_size=window_size,
        stride=stride,
        anomaly_threshold_ratio=0.20,
    )
    train_sequences = builder.build_sequences_from_dataframe(train_df)
    val_sequences = builder.build_sequences_from_dataframe(val_df)
    test_sequences = builder.build_sequences_from_dataframe(test_df)

    logger.info(
        "Constructed sequences: Train=%d (anom=%d), Val=%d (anom=%d), Test=%d (anom=%d)",
        len(train_sequences),
        sum(s.label for s in train_sequences),
        len(val_sequences),
        sum(s.label for s in val_sequences),
        len(test_sequences),
        sum(s.label for s in test_sequences),
    )

    # 5. Create PyTorch Datasets and DataLoaders
    train_dataset = PyTorchLogDataset(train_sequences)
    val_dataset = PyTorchLogDataset(val_sequences)
    test_dataset = PyTorchLogDataset(test_sequences)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,  # Safe to shuffle WITHIN the isolated train split
        collate_fn=pad_sequence_collate,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=pad_sequence_collate,
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=pad_sequence_collate,
    )

    # Calculate class weighting for imbalanced loss
    train_labels = train_dataset.labels
    neg_count = np.sum(train_labels == 0)
    pos_count = np.sum(train_labels == 1)
    weight_val = float(neg_count / max(1, pos_count)) if pos_count > 0 else 1.0
    class_weights = torch.tensor([1.0, min(weight_val, 10.0)], dtype=torch.float32)

    mlflow_tracker = MLflowTracker() if track_mlflow else None
    results: Dict[str, Any] = {}

    # =========================================================================
    # Step A: Non-Neural Baseline (Bag-of-Events + Logistic Regression)
    # =========================================================================
    if model_choice in ("all", "baseline"):
        logger.info("\n--- Evaluating Model 1: Non-Neural Baseline (Bag-of-Events) ---")
        baseline = LogEventCountBaseline(vocab_size=len(vocab), ngram_range=(1, 2), random_state=seed)
        t0 = time.time()
        baseline.fit(train_sequences)
        baseline_time = time.time() - t0
        base_test_metrics = baseline.evaluate(test_sequences)
        results["baseline"] = {
            "model_type": "baseline_bag_of_events",
            "training_time": round(baseline_time, 3),
            "test_metrics": base_test_metrics,
        }
        logger.info("Baseline Test Metrics: %s", {k: v for k, v in base_test_metrics.items() if k != "confusion_matrix"})

        if mlflow_tracker:
            mlflow_tracker.log_model_run(
                experiment_key="dl_log_sequence",
                run_name="baseline_bag_of_events",
                params={"model_type": "baseline", "ngram_range": "(1,2)", "classifier": "logistic_regression"},
                metrics={f"test_{k}": float(v) for k, v in base_test_metrics.items() if isinstance(v, (int, float))},
                tags={"model_type": "baseline", "tier": "benchmark"},
            )

    vocab_metadata = {
        "vocab_size": len(vocab),
        "embedding_dim": embedding_dim,
        "hidden_dim": hidden_dim,
        "num_layers": 2,
        "num_classes": 2,
        "bidirectional": True,
    }

    # =========================================================================
    # Step B: PyTorch LSTM Sequence Model
    # =========================================================================
    if model_choice in ("all", "lstm"):
        logger.info("\n--- Training Model 2: PyTorch Bidirectional LSTM Sequence Model ---")
        lstm_model = LogSequenceLSTM(
            vocab_size=len(vocab),
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            num_layers=2,
            num_classes=2,
            bidirectional=True,
            dropout=0.2,
        )
        early_stopping = EarlyStopping(patience=5, min_delta=1e-4, mode="min")
        trainer = PyTorchTrainer(
            model=lstm_model,
            checkpoint_dir=output_dir,
            early_stopping=early_stopping,
            class_weights=class_weights,
            mlflow_tracker=mlflow_tracker,
        )
        lstm_summary = trainer.fit(
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=test_loader,
            epochs=epochs,
            model_name="lstm",
            vocab_metadata={"architecture": "lstm", **vocab_metadata},
        )
        results["lstm"] = lstm_summary

    # =========================================================================
    # Step C: PyTorch GRU Sequence Model
    # =========================================================================
    if model_choice in ("all", "gru"):
        logger.info("\n--- Training Model 3: PyTorch Bidirectional GRU Sequence Model ---")
        gru_model = LogSequenceGRU(
            vocab_size=len(vocab),
            embedding_dim=embedding_dim,
            hidden_dim=hidden_dim,
            num_layers=2,
            num_classes=2,
            bidirectional=True,
            dropout=0.2,
        )
        early_stopping = EarlyStopping(patience=5, min_delta=1e-4, mode="min")
        trainer = PyTorchTrainer(
            model=gru_model,
            checkpoint_dir=output_dir,
            early_stopping=early_stopping,
            class_weights=class_weights,
            mlflow_tracker=mlflow_tracker,
        )
        gru_summary = trainer.fit(
            train_loader=train_loader,
            val_loader=val_loader,
            test_loader=test_loader,
            epochs=epochs,
            model_name="gru",
            vocab_metadata={"architecture": "gru", **vocab_metadata},
        )
        results["gru"] = gru_summary

    # =========================================================================
    # Step D: Comparative Summary & Champion Selection
    # =========================================================================
    logger.info("\n=================================================================")
    logger.info("                 PHASE 4 MODEL BENCHMARK COMPARISON               ")
    logger.info("=================================================================")
    logger.info("%-15s | %-9s | %-9s | %-9s | %-9s | %-9s", "Model", "Accuracy", "Precision", "Recall", "F1 Score", "ROC-AUC")
    logger.info("-" * 72)

    candidates = []
    for model_key in ["baseline", "lstm", "gru"]:
        if model_key in results:
            res = results[model_key]
            m = res.get("test_metrics", {})
            acc = m.get("accuracy", 0.0)
            prec = m.get("precision", 0.0)
            rec = m.get("recall", 0.0)
            f1 = m.get("f1", 0.0)
            roc = m.get("roc_auc", 0.0)
            logger.info("%-15s | %-9.4f | %-9.4f | %-9.4f | %-9.4f | %-9.4f", model_key.upper(), acc, prec, rec, f1, roc)
            candidates.append((model_key, f1, roc))

    logger.info("=================================================================")

    # Select champion (neural candidate with highest F1/ROC-AUC)
    neural_candidates = [c for c in candidates if c[0] in ("lstm", "gru")]
    if neural_candidates:
        neural_candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        champion_name = neural_candidates[0][0]
        logger.info("Selected Champion Sequence Architecture: %s (Test F1: %.4f)", champion_name.upper(), neural_candidates[0][1])

        # Link champion checkpoint to champion_model.pt
        champion_pt = os.path.join(output_dir, f"{champion_name}_best.pt")
        target_champion = os.path.join(output_dir, "champion_model.pt")
        if os.path.exists(champion_pt):
            import shutil
            shutil.copy2(champion_pt, target_champion)
            logger.info("Saved active champion to %s", target_champion)

        # Save metadata manifest
        manifest = {
            "champion_architecture": champion_name,
            "vocab_size": len(vocab),
            "window_size": window_size,
            "stride": stride,
            "results": {
                k: {
                    "test_f1": v.get("test_metrics", {}).get("f1", 0.0),
                    "test_recall": v.get("test_metrics", {}).get("recall", 0.0),
                    "test_precision": v.get("test_metrics", {}).get("precision", 0.0),
                    "test_roc_auc": v.get("test_metrics", {}).get("roc_auc", 0.0),
                }
                for k, v in results.items()
            },
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        }
        with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpsPilot AI Deep Learning Log Sequence Experiment.")
    parser.add_argument("--model", type=str, default="all", choices=["all", "baseline", "lstm", "gru"])
    parser.add_argument("--epochs", type=int, default=12, help="Max training epochs (default: 12)")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size (default: 32)")
    parser.add_argument("--no-mlflow", action="store_true", help="Disable MLflow logging")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()

    run_pipeline(
        model_choice=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        track_mlflow=not args.no_mlflow,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
