"""Configuration settings for Recommendation & Meal Planner Service."""

from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseModel, Field

from services.common.config import load_env_file

# Load root .env file if present
load_env_file()


class PlannerServiceSettings(BaseModel):
    """Runtime configuration for Recommendation & Meal Planner Service."""

    service_name: str = "recommendation-planner"
    service_title: str = "FoodFlow Recommendation & Meal Planner Service"
    version: str = "0.1.0"
    host: str = Field(default_factory=lambda: os.getenv("PLANNER_SERVICE_HOST", os.getenv("HOST", "0.0.0.0")))
    port: int = Field(
        default_factory=lambda: int(os.getenv("PLANNER_SERVICE_PORT", os.getenv("PORT_PLANNER_SERVICE", os.getenv("PORT", "8003"))))
    )
    database_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("PLANNER_SERVICE_DATABASE_URL")
    )
    pool_min_size: int = Field(
        default_factory=lambda: int(os.getenv("PLANNER_DB_POOL_MIN_SIZE", "1"))
    )
    pool_max_size: int = Field(
        default_factory=lambda: int(os.getenv("PLANNER_DB_POOL_MAX_SIZE", "10"))
    )
    pool_timeout: float = Field(
        default_factory=lambda: float(os.getenv("PLANNER_DB_POOL_TIMEOUT", "5.0"))
    )
    expected_db_role: str = "foodflow_planner_user"
    target_schema: str = "meal_planner"
    probe_table: str = "guest_sessions"
    recipe_service_url: str = Field(
        default_factory=lambda: os.getenv("RECIPE_SERVICE_URL", "http://localhost:8002")
    )
    profile_service_url: str = Field(
        default_factory=lambda: os.getenv("PROFILE_SERVICE_URL", "http://localhost:8001")
    )
    http_client_timeout: float = Field(
        default_factory=lambda: float(os.getenv("PLANNER_HTTP_TIMEOUT", "5.0"))
    )
    guest_session_ttl_days: int = Field(
        default_factory=lambda: int(os.getenv("GUEST_SESSION_TTL_DAYS", "30"))
    )


settings = PlannerServiceSettings()
