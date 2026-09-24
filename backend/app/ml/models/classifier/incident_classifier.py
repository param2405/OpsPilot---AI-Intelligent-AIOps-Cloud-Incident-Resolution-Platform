"""Incident domain classification models for OpsPilot AI.

Classifies incoming incidents into failure domains:
  - database
  - application
  - infrastructure
  - network
  - deployment
  - external_dependency

Compares a Logistic Regression linear baseline against an XGBoost gradient-boosted tree model.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
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


INCIDENT_CATEGORIES = [
    "database",
    "application",
    "infrastructure",
    "network",
    "deployment",
    "external_dependency",
]


class IncidentClassifierPipeline:
    """End-to-end incident classification pipeline wrapping feature engineering and classifier."""

    def __init__(
        self,
        algorithm: str = "xgboost",  # "logistic_regression" or "xgboost"
        feature_pipeline: Optional[IncidentFeaturePipeline] = None,
        random_state: int = 42,
    ) -> None:
        self.algorithm = algorithm.lower()
        self.random_state = random_state
        self.feature_pipeline = feature_pipeline or IncidentFeaturePipeline()
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(INCIDENT_CATEGORIES)

        if self.algorithm == "logistic_regression":
            self.model = LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
                C=1.0,
                solver="lbfgs",
                random_state=self.random_state,
            )
        elif self.algorithm == "xgboost":
            self.model = XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.1,
                objective="multi:softprob",
                eval_metric="mlogloss",
                random_state=self.random_state,
                n_jobs=-1,
            )
        else:
            raise ValueError(f"Unsupported algorithm '{self.algorithm}'. Choose 'logistic_regression' or 'xgboost'.")

        self.is_fitted: bool = False

    def fit(self, df: pd.DataFrame, target_col: str = "category") -> IncidentClassifierPipeline:
        """Fit feature extractor and classification model on incident training set."""
        X = self.feature_pipeline.fit_transform(df)
        y = self.label_encoder.transform(df[target_col].values)
        self.model.fit(X, y)
        self.is_fitted = True
        return self

    def predict(self, df: pd.DataFrame) -> List[str]:
        """Predict incident category labels."""
        if not self.is_fitted:
            raise RuntimeError("Classifier pipeline must be fitted before predicting.")
        X = self.feature_pipeline.transform(df)
        y_pred_idx = self.model.predict(X)
        return list(self.label_encoder.inverse_transform(y_pred_idx))

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities."""
        if not self.is_fitted:
            raise RuntimeError("Classifier pipeline must be fitted before predicting.")
        X = self.feature_pipeline.transform(df)
        return self.model.predict_proba(X)

    def predict_single(self, incident_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Online prediction helper for a single incident payload."""
        df = pd.DataFrame([incident_dict])
        probs = self.predict_proba(df)[0]
        pred_idx = int(np.argmax(probs))
        predicted_category = str(self.label_encoder.classes_[pred_idx])
        confidence = float(probs[pred_idx])

        probability_dict = {
            str(cls_name): round(float(prob), 4)
            for cls_name, prob in zip(self.label_encoder.classes_, probs)
        }

        return {
            "category": predicted_category,
            "confidence": round(confidence, 4),
            "probabilities": probability_dict,
        }

    def evaluate(self, df_test: pd.DataFrame, target_col: str = "category") -> Dict[str, Any]:
        """Compute comprehensive multi-class evaluation metrics."""
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

        # Multi-class One-vs-Rest ROC-AUC
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
    def load(cls, filepath: str) -> IncidentClassifierPipeline:
        obj = joblib.load(filepath)
        if not isinstance(obj, IncidentClassifierPipeline):
            raise TypeError(f"Loaded object is not an IncidentClassifierPipeline: {type(obj)}")
        return obj
