"""Database manager instantiation for Recipe & Ingredient Service."""

from __future__ import annotations

from services.common.database import ServiceDatabaseManager
from services.recipe_ingredient.config import settings

db_manager = ServiceDatabaseManager(
    service_name=settings.service_name,
    expected_role=settings.expected_db_role,
    target_schema=settings.target_schema,
    probe_table=settings.probe_table,
    dsn=settings.database_url,
    min_size=settings.pool_min_size,
    max_size=settings.pool_max_size,
    timeout=settings.pool_timeout,
)


def get_db_manager() -> ServiceDatabaseManager:
    """Dependency provider returning the service database manager instance."""
    return db_manager

