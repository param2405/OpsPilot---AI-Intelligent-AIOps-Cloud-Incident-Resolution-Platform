from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="OpsPilot AI API. Phase 1 exposes process and database health only.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": settings.app_name,
            "phase": "1-foundation",
            "docs": "/docs",
            "health": f"{settings.api_v1_prefix}/health",
            "readiness": f"{settings.api_v1_prefix}/health/ready",
        }

    logger.info(
        "Application created (environment=%s, api_prefix=%s)",
        settings.environment,
        settings.api_v1_prefix,
    )
    return app


app = create_app()
