"""Main FastAPI application entry point for Profile & Nutrition Service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

from services.common.cors import configure_cors
from services.common.errors import register_error_handlers
from services.common.logging import setup_service_logger
from services.profile_nutrition.config import settings
from services.profile_nutrition.database import db_manager
from services.profile_nutrition.routers.biometrics import router as biometrics_router
from services.profile_nutrition.routers.health import router as health_router
from services.profile_nutrition.routers.nutrition import router as nutrition_router

logger = setup_service_logger(settings.service_name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    logger.info("Starting %s on port %s...", settings.service_name, settings.port)
    db_manager.open()
    yield
    logger.info("Shutting down %s...", settings.service_name)
    db_manager.close()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.service_title,
        description="Profile & Nutrition Service for the NutriPod nutritional planning platform.",
        version=settings.version,
        lifespan=lifespan,
    )

    # Configure CORS middleware
    configure_cors(app)

    # Register standardized error handlers matching OpenAPI specs
    register_error_handlers(app)

    # Mount routers
    app.include_router(health_router)
    app.include_router(biometrics_router)
    app.include_router(nutrition_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "services.profile_nutrition.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )

