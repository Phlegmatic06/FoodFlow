"""Configuration settings for Profile & Nutrition Service."""

from __future__ import annotations

import os
from typing import Optional
from pydantic import BaseModel, Field

from services.common.config import load_env_file

# Load root .env file if present
load_env_file()


class ProfileServiceSettings(BaseModel):
    """Runtime configuration for Profile & Nutrition Service."""

    service_name: str = "profile-nutrition"
    service_title: str = "FoodFlow Profile & Nutrition Service"
    version: str = "0.1.0"
    host: str = Field(default_factory=lambda: os.getenv("PROFILE_SERVICE_HOST", os.getenv("HOST", "0.0.0.0")))
    port: int = Field(
        default_factory=lambda: int(os.getenv("PROFILE_SERVICE_PORT", os.getenv("PORT_PROFILE_SERVICE", os.getenv("PORT", "8001"))))
    )
    database_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("PROFILE_SERVICE_DATABASE_URL")
    )
    pool_min_size: int = Field(
        default_factory=lambda: int(os.getenv("PROFILE_DB_POOL_MIN_SIZE", "1"))
    )
    pool_max_size: int = Field(
        default_factory=lambda: int(os.getenv("PROFILE_DB_POOL_MAX_SIZE", "10"))
    )
    pool_timeout: float = Field(
        default_factory=lambda: float(os.getenv("PROFILE_DB_POOL_TIMEOUT", "5.0"))
    )
    expected_db_role: str = "foodflow_profile_user"
    target_schema: str = "profile_nutrition"
    probe_table: str = "usda_foods"


settings = ProfileServiceSettings()
