from fastapi import APIRouter

from app.api.v1.endpoints import (
    agent,
    deep_learning,
    deployments,
    health,
    incidents,
    logs,
    metrics,
    ml,
    orchestration,
    rag,
    remediations,
    services,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(services.router)
api_router.include_router(metrics.router)
api_router.include_router(logs.router)
api_router.include_router(deployments.router)
api_router.include_router(incidents.router)
api_router.include_router(ml.router)
api_router.include_router(deep_learning.router)
api_router.include_router(rag.router)
api_router.include_router(agent.router)
api_router.include_router(orchestration.router)
api_router.include_router(remediations.router)


