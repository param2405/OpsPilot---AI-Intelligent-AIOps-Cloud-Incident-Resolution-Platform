"""FastAPI endpoints for OpsPilot AI Machine Learning Engine."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.ml import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    IncidentClassificationRequest,
    IncidentClassificationResponse,
    ModelsOverviewResponse,
    RetrainRequest,
    RetrainResponse,
    SeverityPredictionRequest,
    SeverityPredictionResponse,
)
from app.services.ml_service import MLInferenceService

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


def get_ml_service() -> MLInferenceService:
    return MLInferenceService()


@router.post(
    "/anomaly",
    response_model=AnomalyDetectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect telemetry metric anomaly",
)
def detect_anomaly(
    request: AnomalyDetectionRequest,
    service: MLInferenceService = Depends(get_ml_service),
) -> AnomalyDetectionResponse:
    """Evaluate telemetry metrics using the active Isolation Forest model to detect anomalies."""
    try:
        return service.detect_anomaly(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(exc)}",
        )


@router.post(
    "/classify",
    response_model=IncidentClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify incident failure category",
)
def classify_incident(
    request: IncidentClassificationRequest,
    service: MLInferenceService = Depends(get_ml_service),
) -> IncidentClassificationResponse:
    """Classify an incident into a failure domain (database, application, network, etc.)."""
    try:
        return service.classify_incident(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incident classification failed: {str(exc)}",
        )


@router.post(
    "/severity",
    response_model=SeverityPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict incident severity level",
)
def predict_severity(
    request: SeverityPredictionRequest,
    service: MLInferenceService = Depends(get_ml_service),
) -> SeverityPredictionResponse:
    """Predict incident severity (LOW, MEDIUM, HIGH, CRITICAL) using multimodal incident features."""
    try:
        return service.predict_severity(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Severity prediction failed: {str(exc)}",
        )


@router.get(
    "/models",
    response_model=ModelsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="List active ML models and evaluation metrics",
)
def get_models(
    service: MLInferenceService = Depends(get_ml_service),
) -> ModelsOverviewResponse:
    """Retrieve metadata, active production versions, and evaluation metrics for all registered models."""
    return service.get_models_overview()


@router.post(
    "/retrain",
    response_model=RetrainResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrain ML models",
)
def retrain_models(
    request: RetrainRequest,
    service: MLInferenceService = Depends(get_ml_service),
) -> RetrainResponse:
    """Trigger retraining of specified ML models with MLflow experiment tracking."""
    try:
        return service.retrain(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model retraining failed: {str(exc)}",
        )
