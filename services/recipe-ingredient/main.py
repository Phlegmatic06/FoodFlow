"""Main FastAPI application entry point for Recipe & Ingredient Service."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI

from services.common.cors import configure_cors
from services.common.errors import register_error_handlers
from services.common.logging import setup_service_logger
from services.recipe_ingredient.config import settings
from services.recipe_ingredient.database import db_manager
from services.recipe_ingredient.routers.health import router as health_router
from services.recipe_ingredient.routers.ingredients import router as ingredients_router
from services.recipe_ingredient.routers.recipes import router as recipes_router

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
        description="Recipe & Ingredient Service for the FoodFlow nutritional planning platform.",
        version=settings.version,
        lifespan=lifespan,
    )

    # Configure CORS middleware
    configure_cors(app)

    # Register standardized error handlers matching OpenAPI specs
    register_error_handlers(app)

    # Mount routers
    app.include_router(health_router)
    app.include_router(recipes_router)
    app.include_router(ingredients_router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "services.recipe_ingredient.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )

