"""Explicit, unabstracted PyTorch training pipeline with validation, checkpointing, and MLflow tracking."""

from __future__ import annotations

import copy
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from app.ml.tracking.mlflow_manager import MLflowTracker

logger = logging.getLogger(__name__)


class EarlyStopping:
    """Early stopping monitor to prevent overfitting when validation performance saturates."""

    def __init__(
        self,
        patience: int = 5,
        min_delta: float = 1e-4,
        mode: str = "max",  # 'max' for F1 / accuracy, 'min' for loss
    ) -> None:
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode.lower()
        self.counter = 0
        self.best_score: Optional[float] = None
        self.early_stop = False
        self.best_epoch = 0

    def step(self, current_metric: float, epoch: int) -> bool:
        """Update monitor with current metric. Returns True if this metric is a new best."""
        if self.best_score is None:
            self.best_score = current_metric
            self.best_epoch = epoch
            return True

        improved = False
        if self.mode == "max":
            if current_metric > (self.best_score + self.min_delta):
                improved = True
        else:  # mode == 'min'
            if current_metric < (self.best_score - self.min_delta):
                improved = True

        if improved:
            self.best_score = current_metric
            self.best_epoch = epoch
            self.counter = 0
            return True
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
                logger.info(
                    "Early stopping triggered at epoch %d. Best metric: %.4f at epoch %d",
                    epoch,
                    self.best_score,
                    self.best_epoch,
                )
            return False


class PyTorchTrainer:
    """Explicit PyTorch trainer implementation without third-party abstraction layers.
    
    Provides step-by-step control over:
      - Forward pass
      - Loss computation and backpropagation
      - Gradient clipping
      - Optimizer step and learning rate scheduling
      - Per-epoch validation and evaluation metrics
      - State-dict checkpointing
      - Early stopping restoration
      - MLflow metric curves and artifact tracking
    """

    def __init__(
        self,
        model: nn.Module,
        optimizer: Optional[torch.optim.Optimizer] = None,
        criterion: Optional[nn.Module] = None,
        scheduler: Optional[Any] = None,
        device: Optional[torch.device] = None,
        checkpoint_dir: str = "ml_models/log_sequence",
        early_stopping: Optional[EarlyStopping] = None,
        class_weights: Optional[torch.Tensor] = None,
        mlflow_tracker: Optional[MLflowTracker] = None,
    ) -> None:
        self.device = device or torch.device("cpu")
        self.model = model.to(self.device)
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        # Default optimizer: AdamW with weight decay
        self.optimizer = optimizer or torch.optim.AdamW(
            self.model.parameters(),
            lr=1e-3,
            weight_decay=1e-4,
        )

        # Loss function with optional class weighting to counteract normal vs anomaly imbalance
        if criterion is not None:
            self.criterion = criterion
        elif class_weights is not None:
            self.criterion = nn.CrossEntropyLoss(weight=class_weights.to(self.device))
        else:
            self.criterion = nn.CrossEntropyLoss()

        self.scheduler = scheduler
        self.early_stopping = early_stopping
        self.mlflow_tracker = mlflow_tracker

        self.history: Dict[str, List[float]] = {
            "train_loss": [],
            "val_loss": [],
            "val_f1": [],
            "val_precision": [],
            "val_recall": [],
            "val_accuracy": [],
        }

    def train_epoch(self, dataloader: DataLoader) -> Dict[str, float]:
        """Execute one complete training epoch over the training DataLoader."""
        self.model.train()
        total_loss = 0.0
        all_preds: List[int] = []
        all_targets: List[int] = []

        for batch in dataloader:
            input_ids = batch["input_ids"].to(self.device)
            labels = batch["labels"].to(self.device)

            # 1. Zero out gradients from prior batch
            self.optimizer.zero_grad()

            # 2. Forward pass through model
            logits, _ = self.model(input_ids)

            # 3. Compute loss
            loss = self.criterion(logits, labels)

            # 4. Backpropagation: compute dLoss/dWeight
            loss.backward()

            # 5. Gradient clipping to prevent exploding gradients in recurrent units
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=5.0)

            # 6. Apply parameter updates
            self.optimizer.step()

            total_loss += loss.item() * len(labels)
            preds = torch.argmax(logits, dim=-1).cpu().numpy().tolist()
            all_preds.extend(preds)
            all_targets.extend(labels.cpu().numpy().tolist())

        avg_loss = total_loss / max(1, len(all_targets))
        f1 = float(f1_score(all_targets, all_preds, average="binary" if max(all_targets) <= 1 else "macro", zero_division=0))
        return {"loss": avg_loss, "f1": f1}

    def validate(self, dataloader: DataLoader) -> Dict[str, Any]:
        """Execute validation without gradient tracking and compute comprehensive metrics."""
        self.model.eval()
        total_loss = 0.0
        all_preds: List[int] = []
        all_targets: List[int] = []
        all_probas: List[List[float]] = []

        with torch.no_grad():
            for batch in dataloader:
                input_ids = batch["input_ids"].to(self.device)
                labels = batch["labels"].to(self.device)

                logits, _ = self.model(input_ids)
                loss = self.criterion(logits, labels)

                total_loss += loss.item() * len(labels)
                probas = torch.softmax(logits, dim=-1).cpu().numpy()
                preds = np.argmax(probas, axis=-1).tolist()

                all_preds.extend(preds)
                all_targets.extend(labels.cpu().numpy().tolist())
                all_probas.extend(probas.tolist())

        avg_loss = total_loss / max(1, len(all_targets))
        y_true = np.array(all_targets)
        y_pred = np.array(all_preds)
        y_proba = np.array(all_probas)

        acc = float(accuracy_score(y_true, y_pred))
        is_binary = len(np.unique(y_true)) <= 2 and max(all_targets) <= 1
        avg_mode = "binary" if is_binary else "macro"

        prec = float(precision_score(y_true, y_pred, average=avg_mode, zero_division=0))
        rec = float(recall_score(y_true, y_pred, average=avg_mode, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, average=avg_mode, zero_division=0))

        roc_auc = 0.0
        if len(np.unique(y_true)) > 1:
            try:
                if is_binary and y_proba.shape[1] >= 2:
                    roc_auc = float(roc_auc_score(y_true, y_proba[:, 1]))
                elif y_proba.shape[1] > 2:
                    roc_auc = float(roc_auc_score(y_true, y_proba, multi_class="ovr"))
            except Exception:
                roc_auc = 0.0

        cm = confusion_matrix(y_true, y_pred, labels=[0, 1] if is_binary else None).tolist()

        return {
            "loss": round(avg_loss, 4),
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "roc_auc": round(roc_auc, 4),
            "confusion_matrix": cm,
            "sample_count": len(all_targets),
        }

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        test_loader: Optional[DataLoader] = None,
        epochs: int = 15,
        model_name: str = "lstm",
        vocab_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Full training loop orchestration across epochs with checkpointing and early stopping."""
        logger.info(
            "Starting explicit PyTorch training loop for '%s' (epochs=%d, device=%s)",
            model_name,
            epochs,
            self.device,
        )

        best_weights = copy.deepcopy(self.model.state_dict())
        best_val_f1 = -1.0
        best_val_loss = float("inf")
        best_epoch = 1
        start_time = time.time()

        for epoch in range(1, epochs + 1):
            epoch_start = time.time()
            # 1. Train epoch
            train_metrics = self.train_epoch(train_loader)

            # 2. Validation epoch
            val_metrics = self.validate(val_loader)

            epoch_dur = time.time() - epoch_start

            # Record history
            self.history["train_loss"].append(train_metrics["loss"])
            self.history["val_loss"].append(val_metrics["loss"])
            self.history["val_f1"].append(val_metrics["f1"])
            self.history["val_precision"].append(val_metrics["precision"])
            self.history["val_recall"].append(val_metrics["recall"])
            self.history["val_accuracy"].append(val_metrics["accuracy"])

            logger.info(
                "Epoch %02d/%02d [%.2fs] — Train Loss: %.4f | Val Loss: %.4f | Val F1: %.4f | Val Rec: %.4f",
                epoch,
                epochs,
                epoch_dur,
                train_metrics["loss"],
                val_metrics["loss"],
                val_metrics["f1"],
                val_metrics["recall"],
            )

            # Learning rate scheduler step
            if self.scheduler is not None:
                if isinstance(self.scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
                    self.scheduler.step(val_metrics["loss"])
                else:
                    self.scheduler.step()

            # Check if new best: higher F1, or equal F1 with lower validation loss
            is_better = (val_metrics["f1"] > best_val_f1) or (
                abs(val_metrics["f1"] - best_val_f1) < 1e-5 and val_metrics["loss"] < best_val_loss
            )
            if is_better:
                best_val_f1 = val_metrics["f1"]
                best_val_loss = val_metrics["loss"]
                best_epoch = epoch
                best_weights = copy.deepcopy(self.model.state_dict())

                # Checkpoint best model
                checkpoint_path = os.path.join(self.checkpoint_dir, f"{model_name}_best.pt")
                self.save_checkpoint(
                    filepath=checkpoint_path,
                    epoch=epoch,
                    metrics=val_metrics,
                    extra_data=vocab_metadata,
                )

            # Early stopping check
            if self.early_stopping is not None:
                monitor_val = val_metrics["loss"] if self.early_stopping.mode == "min" else val_metrics["f1"]
                self.early_stopping.step(monitor_val, epoch=epoch)
                if self.early_stopping.early_stop:
                    logger.info("Early stopping triggered at epoch %d", epoch)
                    break

        # Restore best model weights
        logger.info("Restoring best model weights from epoch %d (Val F1: %.4f)", best_epoch, best_val_f1)
        self.model.load_state_dict(best_weights)

        # Final evaluation on held-out test split
        test_metrics: Dict[str, Any] = {}
        if test_loader is not None:
            test_metrics = self.validate(test_loader)
            logger.info(
                "Final Held-Out Test Evaluation (%s) — F1: %.4f | Precision: %.4f | Recall: %.4f | ROC-AUC: %.4f",
                model_name,
                test_metrics["f1"],
                test_metrics["precision"],
                test_metrics["recall"],
                test_metrics["roc_auc"],
            )

        total_training_time = time.time() - start_time

        summary = {
            "model_name": model_name,
            "best_epoch": best_epoch,
            "total_epochs_trained": len(self.history["train_loss"]),
            "training_time_seconds": round(total_training_time, 2),
            "best_val_f1": round(best_val_f1, 4),
            "test_metrics": test_metrics,
            "history": self.history,
        }

        # MLflow experiment logging if enabled
        if self.mlflow_tracker is not None:
            try:
                self._log_to_mlflow(model_name, summary, test_metrics)
            except Exception as exc:
                logger.warning("MLflow logging encountered warning: %s", exc)

        return summary

    def save_checkpoint(
        self,
        filepath: str,
        epoch: int,
        metrics: Dict[str, Any],
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Serialize full model checkpoint including weights, optimizer state, and metadata."""
        checkpoint = {
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "metrics": metrics,
            "extra_data": extra_data or {},
        }
        torch.save(checkpoint, filepath)
        logger.debug("Saved PyTorch checkpoint to %s", filepath)

    def load_checkpoint(self, filepath: str) -> Dict[str, Any]:
        """Load weights and checkpoint payload from file."""
        checkpoint = torch.load(filepath, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        if "optimizer_state_dict" in checkpoint and self.optimizer:
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        logger.info("Loaded PyTorch model checkpoint from %s (epoch %d)", filepath, checkpoint.get("epoch", -1))
        return checkpoint

    def _log_to_mlflow(
        self,
        model_name: str,
        summary: Dict[str, Any],
        test_metrics: Dict[str, Any],
    ) -> None:
        """Record deep learning run parameters, metrics, and artifact references to MLflow."""
        if self.mlflow_tracker is None:
            return

        params = {
            "architecture": model_name,
            "vocab_size": getattr(self.model, "vocab_size", "unknown"),
            "embedding_dim": getattr(self.model, "embedding_dim", "unknown"),
            "hidden_dim": getattr(self.model, "hidden_dim", "unknown"),
            "num_layers": getattr(self.model, "num_layers", "unknown"),
            "bidirectional": getattr(self.model, "bidirectional", "unknown"),
            "total_epochs": summary.get("total_epochs_trained", 0),
        }

        # Log final metrics
        metrics_to_log: Dict[str, float] = {
            "best_val_f1": float(summary.get("best_val_f1", 0.0)),
            "training_time_sec": float(summary.get("training_time_seconds", 0.0)),
        }
        for k in ["accuracy", "precision", "recall", "f1", "roc_auc", "loss"]:
            if k in test_metrics:
                metrics_to_log[f"test_{k}"] = float(test_metrics[k])

        run_id = self.mlflow_tracker.log_model_run(
            experiment_key="dl_log_sequence",
            run_name=f"{model_name}_sequence_model",
            params=params,
            metrics=metrics_to_log,
            tags={"model_type": "deep_learning_sequence", "architecture": model_name},
        )
        logger.info("Logged deep learning run '%s' to MLflow (Run ID: %s)", model_name, run_id)
