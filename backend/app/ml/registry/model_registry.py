"""Model Registry and Version Management for OpsPilot AI.

Manages model versions, manifests, active production aliases, and artifact loading.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib


DEFAULT_REGISTRY_DIR = Path(__file__).resolve().parents[3] / "ml_models"


class ModelRegistry:
    """Production Model Registry managing versioned artifacts and deployment manifests."""

    def __init__(self, registry_dir: Optional[Path] = None) -> None:
        self.registry_dir = registry_dir or DEFAULT_REGISTRY_DIR
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.registry_dir / "manifest.json"
        self._cache: Dict[str, Any] = {}

    def _read_manifest(self) -> Dict[str, Any]:
        if not self.manifest_path.exists():
            return {"models": {}}
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"models": {}}

    def _write_manifest(self, data: Dict[str, Any]) -> None:
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def register_model(
        self,
        model_name: str,  # "anomaly", "classification", "severity"
        version: str,
        algorithm: str,
        model_obj: Any,
        metrics: Dict[str, Any],
        mlflow_run_id: Optional[str] = None,
        feature_pipeline: Optional[Any] = None,
        set_active: bool = True,
    ) -> str:
        """Persist model and optional feature pipeline to registry and update manifest."""
        model_subfolder = self.registry_dir / model_name
        model_subfolder.mkdir(parents=True, exist_ok=True)

        artifact_filename = f"{algorithm}_{version}.joblib"
        artifact_path = model_subfolder / artifact_filename
        joblib.dump(model_obj, artifact_path)

        fp_filename = None
        if feature_pipeline is not None:
            fp_filename = f"feature_pipeline_{version}.joblib"
            fp_path = model_subfolder / fp_filename
            joblib.dump(feature_pipeline, fp_path)

        manifest = self._read_manifest()
        if "models" not in manifest:
            manifest["models"] = {}

        if model_name not in manifest["models"]:
            manifest["models"][model_name] = {"versions": {}, "active_version": None}

        version_info = {
            "version": version,
            "algorithm": algorithm,
            "artifact_file": artifact_filename,
            "feature_pipeline_file": fp_filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "mlflow_run_id": mlflow_run_id,
            "metrics": metrics,
        }

        manifest["models"][model_name]["versions"][version] = version_info
        if set_active or manifest["models"][model_name]["active_version"] is None:
            manifest["models"][model_name]["active_version"] = version

        self._write_manifest(manifest)

        # Invalidate cache
        if model_name in self._cache:
            del self._cache[model_name]

        return str(artifact_path)

    def get_active_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get manifest entry for current active version of model."""
        manifest = self._read_manifest()
        model_entry = manifest.get("models", {}).get(model_name)
        if not model_entry:
            return None
        active_ver = model_entry.get("active_version")
        if not active_ver:
            return None
        info = model_entry.get("versions", {}).get(active_ver)
        if info:
            info["active_version"] = active_ver
        return info

    def load_active_model(self, model_name: str) -> Tuple[Any, Optional[Any]]:
        """Load and cache the active production model and its feature pipeline.
        
        Returns:
            Tuple of (model_object, feature_pipeline_or_None)
        """
        if model_name in self._cache:
            return self._cache[model_name]

        info = self.get_active_model_info(model_name)
        if not info:
            raise FileNotFoundError(f"No active model registered for '{model_name}'. Train models first.")

        model_subfolder = self.registry_dir / model_name
        artifact_path = model_subfolder / info["artifact_file"]
        if not artifact_path.exists():
            raise FileNotFoundError(f"Model artifact not found at {artifact_path}")

        model_obj = joblib.load(artifact_path)

        fp_obj = None
        if info.get("feature_pipeline_file"):
            fp_path = model_subfolder / info["feature_pipeline_file"]
            if fp_path.exists():
                fp_obj = joblib.load(fp_path)

        self._cache[model_name] = (model_obj, fp_obj)
        return model_obj, fp_obj

    def list_models(self) -> Dict[str, Any]:
        """List all models and their version history."""
        return self._read_manifest().get("models", {})
