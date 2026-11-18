"""Inter-service REST API client for Recipe Service and Profile Service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
import httpx

from services.recommendation_planner.config import settings

logger = logging.getLogger(f"foodflow.{settings.service_name}")


class ServiceCommunicationError(Exception):
    """Base exception for upstream service failures."""

    def __init__(self, service_name: str, status_code: int, message: str) -> None:
        self.service_name = service_name
        self.status_code = status_code
        self.message = message
        super().__init__(f"[{service_name}] HTTP {status_code}: {message}")


class UpstreamServiceUnavailableError(ServiceCommunicationError):
    """Raised when an upstream service cannot be reached (connection error or timeout)."""

    def __init__(self, service_name: str, message: str) -> None:
        super().__init__(service_name, 502, message)


class RecipeServiceClient:
    """REST client for communicating with Recipe & Ingredient Service (Port 8002)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or settings.recipe_service_url).rstrip("/")
        self.timeout = timeout or settings.http_client_timeout

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": f"NutriPod-Planner/{settings.version}",
        }

    def normalize_ingredients(self, ingredients: List[str]) -> Dict[str, Any]:
        """POST /api/v1/ingredients/normalize. Maps raw ingredient text to canonical taxonomy."""
        url = f"{self.base_url}/api/v1/ingredients/normalize"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    json={"ingredients": ingredients},
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    return resp.json()
                raise ServiceCommunicationError("recipe-service", resp.status_code, resp.text)
        except httpx.RequestError as exc:
            logger.warning("Recipe service connection failed on normalize: %s", exc)
            raise UpstreamServiceUnavailableError(
                "recipe-service", f"Failed to connect to Recipe Service: {exc}"
            ) from exc

    def search_by_ingredients(
        self,
        ingredient_ids: List[int],
        min_match_ratio: float = 0.3,
        limit: int = 24,
    ) -> Dict[str, Any]:
        """POST /api/v1/recipes/search-by-ingredients. Finds recipes by canonical ingredient IDs."""
        url = f"{self.base_url}/api/v1/recipes/search-by-ingredients"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    json={
                        "canonical_ingredient_ids": ingredient_ids,
                        "ingredient_ids": ingredient_ids,
                        "min_match_pct": min_match_ratio * 100.0,
                        "min_match_ratio": min_match_ratio,
                        "limit": limit,
                    },
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    return resp.json()
                raise ServiceCommunicationError("recipe-service", resp.status_code, resp.text)
        except httpx.RequestError as exc:
            logger.warning("Recipe service connection failed on search-by-ingredients: %s", exc)
            raise UpstreamServiceUnavailableError(
                "recipe-service", f"Failed to connect to Recipe Service: {exc}"
            ) from exc

    def batch_get_recipes(self, recipe_ids: List[str]) -> Dict[str, Any]:
        """POST /api/v1/recipes/batch. Bulk fetch recipe records by ID list."""
        if not recipe_ids:
            return {"recipes": [], "missing_ids": []}
        url = f"{self.base_url}/api/v1/recipes/batch"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    json={"recipe_ids": recipe_ids},
                    headers=self._get_headers(),
                )
                if resp.status_code == 200:
                    return resp.json()
                raise ServiceCommunicationError("recipe-service", resp.status_code, resp.text)
        except httpx.RequestError as exc:
            logger.warning("Recipe service connection failed on batch_get_recipes: %s", exc)
            raise UpstreamServiceUnavailableError(
                "recipe-service", f"Failed to connect to Recipe Service: {exc}"
            ) from exc

    def get_recipe(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/recipes/{recipe_id}. Fetch full detail for a single recipe."""
        url = f"{self.base_url}/api/v1/recipes/{recipe_id}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 404:
                    return None
                raise ServiceCommunicationError("recipe-service", resp.status_code, resp.text)
        except httpx.RequestError as exc:
            logger.warning("Recipe service connection failed on get_recipe: %s", exc)
            raise UpstreamServiceUnavailableError(
                "recipe-service", f"Failed to connect to Recipe Service: {exc}"
            ) from exc

    def search_recipes(
        self,
        q: Optional[str] = None,
        cuisine: Optional[str] = None,
        diet: Optional[str] = None,
        max_time: Optional[int] = None,
        page: int = 1,
        limit: int = 24,
    ) -> Dict[str, Any]:
        """GET /api/v1/recipes/search. Search catalogue by filters."""
        url = f"{self.base_url}/api/v1/recipes/search"
        params: Dict[str, Any] = {"page": page, "page_size": limit}
        if q:
            params["q"] = q
        if cuisine:
            params["cuisine"] = cuisine
        if diet:
            params["diet"] = diet
        if max_time:
            params["max_time"] = max_time

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params, headers=self._get_headers())
                if resp.status_code == 200:
                    return resp.json()
                raise ServiceCommunicationError("recipe-service", resp.status_code, resp.text)
        except httpx.RequestError as exc:
            logger.warning("Recipe service connection failed on search_recipes: %s", exc)
            raise UpstreamServiceUnavailableError(
                "recipe-service", f"Failed to connect to Recipe Service: {exc}"
            ) from exc


class ProfileServiceClient:
    """REST client for communicating with Profile & Nutrition Service (Port 8001)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.base_url = (base_url or settings.profile_service_url).rstrip("/")
        self.timeout = timeout or settings.http_client_timeout

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "User-Agent": f"NutriPod-Planner/{settings.version}",
        }

    def get_cached_recipe_nutrition(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """GET /api/v1/nutrition/recipes/{recipe_id}. Retrieve cached nutrition estimate."""
        url = f"{self.base_url}/api/v1/nutrition/recipes/{recipe_id}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._get_headers())
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 404:
                    return None
                raise ServiceCommunicationError("profile-service", resp.status_code, resp.text)
        except httpx.RequestError as exc:
            logger.warning("Profile service connection failed on get_cached_nutrition: %s", exc)
            return None
