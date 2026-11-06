"""USDA FoodData Central lookup and recipe nutrition estimation endpoints."""

from __future__ import annotations

import math
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from services.common.database import ServiceDatabaseManager
from services.profile_nutrition.database import get_db_manager
from services.profile_nutrition.estimator import estimate_recipe_nutrition
from services.profile_nutrition.repository import ProfileRepository
from services.profile_nutrition.schemas import (
    CachedRecipeNutrition,
    PaginatedUSDAFoodSummary,
    PaginationInfo,
    RecipeNutritionEstimateRequest,
    RecipeNutritionEstimateResponse,
    USDAFoodDetail,
)

router = APIRouter(prefix="/api/v1/nutrition", tags=["USDA FoodData", "Recipe Nutrition"])


def get_repository(
    db: ServiceDatabaseManager = Depends(get_db_manager),
) -> ProfileRepository:
    """Dependency provider returning a ProfileRepository instance."""
    return ProfileRepository(db)


@router.get(
    "/foods/search",
    response_model=PaginatedUSDAFoodSummary,
    status_code=status.HTTP_200_OK,
    tags=["USDA FoodData"],
    summary="Search USDA FoodData Central items",
    description="Full-text and keyword query against imported USDA foods.",
)
def search_usda_foods(
    q: str = Query(..., min_length=1, max_length=255, description="Search term or food description prefix"),
    data_type: Optional[Literal["foundation_food", "sr_legacy_food", "survey_fndds_food"]] = Query(
        None, description="Optional filter by USDA dataset sub-type"
    ),
    page: int = Query(1, ge=1, description="1-indexed page number"),
    limit: int = Query(24, ge=1, le=48, description="Maximum items per page"),
    repo: ProfileRepository = Depends(get_repository),
) -> PaginatedUSDAFoodSummary:
    """Public USDA food search endpoint."""
    clean_q = q.strip()
    if not clean_q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' must not be empty",
        )

    foods, total_items = repo.search_usda_foods(
        q=clean_q,
        data_type=data_type,
        page=page,
        limit=limit,
    )
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0

    return PaginatedUSDAFoodSummary(
        data=foods,
        pagination=PaginationInfo(
            page=page,
            limit=limit,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/foods/{fdc_id}",
    response_model=USDAFoodDetail,
    status_code=status.HTTP_200_OK,
    tags=["USDA FoodData"],
    summary="Retrieve complete USDA food nutrient profile",
    description=(
        "Returns food description, all laboratory nutrient measurements per 100g, "
        "and standard household portions."
    ),
)
def get_usda_food_detail(
    fdc_id: int = Path(..., description="Authoritative USDA FoodData Central integer identifier"),
    repo: ProfileRepository = Depends(get_repository),
) -> USDAFoodDetail:
    """Public USDA food detail endpoint."""
    food = repo.get_usda_food_detail(fdc_id)
    if not food:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"USDA food item with fdc_id {fdc_id} was not found",
        )
    return food


@router.post(
    "/recipes/estimate",
    response_model=RecipeNutritionEstimateResponse,
    status_code=status.HTTP_200_OK,
    tags=["Recipe Nutrition"],
    summary="Calculate nutrient profile from raw ingredients",
    description=(
        "Receives recipe ingredients, maps them against USDA food nutrient composition tables, "
        "and aggregates nutritional values without fabricating missing values."
    ),
)
def estimate_nutrition(
    payload: RecipeNutritionEstimateRequest,
    repo: ProfileRepository = Depends(get_repository),
) -> RecipeNutritionEstimateResponse:
    """Recipe nutrition estimation endpoint."""
    return estimate_recipe_nutrition(payload, repo)


@router.get(
    "/recipes/{recipe_id}",
    response_model=CachedRecipeNutrition,
    status_code=status.HTTP_200_OK,
    tags=["Recipe Nutrition"],
    summary="Get cached recipe nutritional profile",
    description="Retrieves nutritional values stored in profile_nutrition.nutrition_estimates by recipe_id.",
)
def get_cached_nutrition(
    recipe_id: str = Path(
        ...,
        pattern=r"^rcp_(foodcom|nlg)_[a-zA-Z0-9_-]+$",
        description="Unified recipe identifier",
    ),
    repo: ProfileRepository = Depends(get_repository),
) -> CachedRecipeNutrition:
    """Cached recipe nutrition retrieval endpoint."""
    cached = repo.get_cached_recipe_nutrition(recipe_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No nutrition estimate cached for recipe '{recipe_id}'",
        )
    return cached

