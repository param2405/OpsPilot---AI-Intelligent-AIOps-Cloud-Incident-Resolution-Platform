from fastapi import APIRouter

from app.api.v1.endpoints import deployments, health, incidents, logs, metrics, services

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(services.router)
api_router.include_router(metrics.router)
api_router.include_router(logs.router)
api_router.include_router(deployments.router)
api_router.include_router(incidents.router)
