"""Incident severity prediction model for OpsPilot AI.

Predicts operational incident severity levels:
  - LOW
  - MEDIUM
  - HIGH
  - CRITICAL

Uses gradient-boosted decision trees (XGBoost) trained on multimodal incident features
combining textual symptoms with onset telemetry metrics.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from app.ml.features.incident import IncidentFeaturePipeline


SEVERITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class SeverityPredictorPipeline:
    """Predicts incident severity tier from multimodal text and telemetry context."""

    def __init__(
        self,
        feature_pipeline: Optional[IncidentFeaturePipeline] = None,
        n_estimators: int = 120,
        max_depth: int = 4,
        learning_rate: float = 0.08,
        random_state: int = 42,
    ) -> None:
        self.feature_pipeline = feature_pipeline or IncidentFeaturePipeline()
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(SEVERITY_LEVELS)

        self.model = XGBClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            objective="multi:softprob",
            eval_metric="mlogloss",
            random_state=random_state,
            n_jobs=-1,
        )
        self.is_fitted: bool = False

    def fit(self, df: pd.DataFrame, target_col: str = "severity") -> SeverityPredictorPipeline:
        """Fit feature extractor and severity classifier on incident training partition."""
        X = self.feature_pipeline.fit_transform(df)
        y = self.label_encoder.transform(df[target_col].values)
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> List[str]:
        if not self.is_fitted:
            raise RuntimeError("Severity predictor must be fitted before predicting.")
        X = self.feature_pipeline.transform(df)
        y_pred_idx = self.model.predict(X)
        return list(self.label_encoder.inverse_transform(y_pred_idx))

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        if not self.is_fitted:
            raise RuntimeError("Severity predictor must be fitted before predicting.")
        X = self.feature_pipeline.transform(df)
        return self.model.predict_proba(X)

    def predict_single(self, incident_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Online prediction helper extracting predicted severity, confidence, and risk factors."""
        df = pd.DataFrame([incident_dict])
        probs = self.predict_proba(df)[0]
        pred_idx = int(np.argmax(probs))
        predicted_severity = str(self.label_encoder.classes_[pred_idx])
        confidence = float(probs[pred_idx])

        probability_dict = {
            str(lvl): round(float(prob), 4)
            for lvl, prob in zip(self.label_encoder.classes_, probs)
        }

        # Analyze risk factors from inputs
        risk_factors: List[str] = []
        err = float(incident_dict.get("error_rate") or 0.0)
        lat = float(incident_dict.get("latency_p95_ms") or 0.0)
        cpu = float(incident_dict.get("cpu_usage") or 0.0)
        mem = float(incident_dict.get("memory_usage") or 0.0)
        tier = str(incident_dict.get("tier") or "").lower()

        if tier == "critical":
            risk_factors.append("Critical-tier service affected")
        if err > 0.15:
            risk_factors.append(f"Elevated error rate ({round(err * 100, 1)}%)")
        if lat > 1500:
            risk_factors.append(f"Severe p95 latency degradation ({round(lat, 0)}ms)")
        if cpu > 85.0:
            risk_factors.append(f"High CPU saturation ({round(cpu, 1)}%)")
        if mem > 85.0:
            risk_factors.append(f"High memory saturation ({round(mem, 1)}%)")

        if not risk_factors:
            risk_factors.append("Nominal metric baseline; localized impact")

        return {
            "severity": predicted_severity,
            "confidence": round(confidence, 4),
            "probabilities": probability_dict,
            "risk_factors": risk_factors,
        }

    def evaluate(self, df_test: pd.DataFrame, target_col: str = "severity") -> Dict[str, Any]:
        """Compute evaluation metrics on held-out test partition."""
        y_true_str = df_test[target_col].values
        y_true = self.label_encoder.transform(y_true_str)

        X_test = self.feature_pipeline.transform(df_test)
        y_pred = self.model.predict(X_test)
        y_proba = self.model.predict_proba(X_test)

        acc = float(accuracy_score(y_true, y_pred))
        macro_f1 = float(f1_score(y_true, y_pred, average="macro"))
        weighted_f1 = float(f1_score(y_true, y_pred, average="weighted"))
        macro_prec = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
        macro_rec = float(recall_score(y_true, y_pred, average="macro", zero_division=0))

        try:
            roc_auc = float(roc_auc_score(y_true, y_proba, multi_class="ovr", average="macro"))
        except Exception:
            roc_auc = 0.0

        cm = confusion_matrix(y_true, y_pred).tolist()

        return {
            "accuracy": round(acc, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "macro_precision": round(macro_prec, 4),
            "macro_recall": round(macro_rec, 4),
            "roc_auc_ovr": round(roc_auc, 4),
            "confusion_matrix": cm,
            "classes": list(self.label_encoder.classes_),
        }

    def save(self, filepath: str) -> None:
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath: str) -> SeverityPredictorPipeline:
        obj = joblib.load(filepath)
        if not isinstance(obj, SeverityPredictorPipeline):
            raise TypeError(f"Loaded object is not a SeverityPredictorPipeline: {type(obj)}")
        return obj
