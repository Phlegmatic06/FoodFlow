"""Main FastAPI application entry point for Recommendation & Meal Planner Service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

from services.common.cors import configure_cors
from services.common.errors import register_error_handlers
from services.common.logging import setup_service_logger
from services.recommendation_planner.config import settings
from services.recommendation_planner.database import db_manager
from services.recommendation_planner.routers.health import router as health_router
from services.recommendation_planner.routers.pantry import router as pantry_router
from services.recommendation_planner.routers.plans import router as plans_router
from services.recommendation_planner.routers.sessions import router as sessions_router
from services.recommendation_planner.routers.shopping import router as shopping_router

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
        description="Recommendation & Meal Planner Service for the FoodFlow nutritional planning platform.",
        version=settings.version,
        lifespan=lifespan,
    )

    # Configure CORS middleware
    configure_cors(app)

    # Register standardized error handlers matching OpenAPI specs
    register_error_handlers(app)

    # Mount routers
    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(pantry_router)
    app.include_router(plans_router)
    app.include_router(shopping_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "services.recommendation_planner.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )

