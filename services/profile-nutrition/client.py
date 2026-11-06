"""REST HTTP client for inter-service communication with Recipe & Ingredient Service."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("foodflow.profile-nutrition.client")

RECIPE_SERVICE_URL = os.getenv("RECIPE_SERVICE_URL", "http://localhost:8002").rstrip("/")


class RecipeServiceClient:
    """Client for retrieving recipe details from Service 2 over internal REST network."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0) -> None:
        self.base_url = (base_url or RECIPE_SERVICE_URL).rstrip("/")
        self.timeout = timeout

    def get_recipe_detail(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """Fetch recipe record from Recipe Service via GET /api/v1/recipes/{recipe_id}."""
        target_url = f"{self.base_url}/api/v1/recipes/{recipe_id}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(target_url)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 404:
                    return None
                else:
                    logger.warning(
                        "Upstream Recipe Service returned non-200 status: %s for recipe %s",
                        resp.status_code,
                        recipe_id,
                    )
                    return None
        except httpx.RequestError as exc:
            logger.warning("Failed to reach upstream Recipe Service at %s: %s", self.base_url, exc)
            return None


recipe_client = RecipeServiceClient()


def get_recipe_client() -> RecipeServiceClient:
    """Dependency provider for RecipeServiceClient."""
    return recipe_client

