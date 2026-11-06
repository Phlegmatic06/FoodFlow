"""Recipe discovery, catalogue search, detail, batch, and ingredient candidate endpoints."""

from __future__ import annotations

import math
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from services.common.database import ServiceDatabaseManager
from services.recipe_ingredient.database import get_db_manager
from services.recipe_ingredient.repository import RecipeRepository
from services.recipe_ingredient.schemas import (
    BatchRecipeRequest,
    BatchRecipeResponse,
    PaginatedIngredientCandidates,
    PaginatedRecipeSummary,
    PaginationInfo,
    RecipeDetail,
    SearchByIngredientsRequest,
)

router = APIRouter(prefix="/api/v1/recipes", tags=["Recipe Discovery"])


def get_repository(
    db: ServiceDatabaseManager = Depends(get_db_manager),
) -> RecipeRepository:
    """Dependency provider returning a RecipeRepository instance."""
    return RecipeRepository(db)


@router.get(
    "/search",
    response_model=PaginatedRecipeSummary,
    status_code=status.HTTP_200_OK,
    summary="Search and filter recipe catalogue",
    description=(
        "Full-text search powered by PostgreSQL tsvector over titles, descriptions, and tags. "
        "Supports faceted filtering by cuisine, dietary tags, total time, and dataset source."
    ),
)
def search_recipes(
    q: Optional[str] = Query(None, description="Free-text search terms"),
    cuisine: Optional[str] = Query(None, description="Filter by cuisine name"),
    tag: Optional[str] = Query(None, description="Filter by specific recipe tag"),
    diet: Optional[str] = Query(
        None, description="Filter by dietary category tag (e.g., vegetarian, vegan, gluten-free)"
    ),
    max_time: Optional[int] = Query(
        None, ge=1, description="Maximum total preparation and cooking time in minutes"
    ),
    source_dataset: Optional[Literal["food_com", "recipenlg"]] = Query(
        None, description="Filter by original dataset corpus"
    ),
    sort: Literal["relevance", "rating", "time_asc", "time_desc"] = Query(
        "relevance", description="Ordering criteria for results"
    ),
    page: int = Query(1, ge=1, description="1-indexed page number"),
    limit: int = Query(24, ge=1, le=48, description="Items per page (max 48)"),
    repo: RecipeRepository = Depends(get_repository),
) -> PaginatedRecipeSummary:
    """Public recipe discovery endpoint."""
    recipes, total_items = repo.search_recipes(
        q=q,
        cuisine=cuisine,
        tag=tag,
        diet=diet,
        max_time=max_time,
        source_dataset=source_dataset,
        sort=sort,
        page=page,
        limit=limit,
    )
    total_pages = math.ceil(total_items / limit) if total_items > 0 else 0
    return PaginatedRecipeSummary(
        data=recipes,
        pagination=PaginationInfo(
            page=page,
            limit=limit,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{recipe_id}",
    response_model=RecipeDetail,
    status_code=status.HTTP_200_OK,
    summary="Retrieve complete recipe details",
    description=(
        "Returns complete recipe record including ordered ingredient items with raw strings, "
        "ordered cooking steps, tags, ratings, and raw dataset nutrition values when present."
    ),
)
def get_recipe_detail(
    recipe_id: str = Path(
        ...,
        pattern=r"^rcp_(foodcom|nlg)_[a-zA-Z0-9_-]+$",
        description="Unified global recipe identifier",
    ),
    repo: RecipeRepository = Depends(get_repository),
) -> RecipeDetail:
    """Public recipe detail endpoint."""
    recipe = repo.get_recipe_detail(recipe_id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipe '{recipe_id}' was not found",
        )
    return recipe


@router.post(
    "/batch",
    response_model=BatchRecipeResponse,
    status_code=status.HTTP_200_OK,
    tags=["Internal Services"],
    summary="Batch retrieve recipe records by ID list",
    description="Internal endpoint designed for Service 3 (Recommendation & Meal Planner).",
)
def batch_get_recipes(
    payload: BatchRecipeRequest,
    repo: RecipeRepository = Depends(get_repository),
) -> BatchRecipeResponse:
    """Batch recipe lookup endpoint."""
    recipes, not_found = repo.batch_get_recipes(payload.recipe_ids, payload.fields)
    return BatchRecipeResponse(recipes=recipes, not_found=not_found)


@router.post(
    "/search-by-ingredients",
    response_model=PaginatedIngredientCandidates,
    status_code=status.HTTP_200_OK,
    tags=["Internal Services"],
    summary="Candidate recipe retrieval by canonical ingredient IDs",
    description="Internal service-to-service endpoint for candidate matching in Service 3.",
)
def search_recipes_by_ingredients(
    payload: SearchByIngredientsRequest,
    repo: RecipeRepository = Depends(get_repository),
) -> PaginatedIngredientCandidates:
    """Ingredient-based candidate recipe retrieval."""
    candidates, total_items = repo.search_recipes_by_ingredients(
        canonical_ingredient_ids=payload.canonical_ingredient_ids,
        exclude_pantry_staples=payload.exclude_pantry_staples,
        min_match_pct=payload.min_match_pct,
        page=payload.page,
        limit=payload.limit,
    )
    total_pages = math.ceil(total_items / payload.limit) if total_items > 0 else 0
    return PaginatedIngredientCandidates(
        data=candidates,
        pagination=PaginationInfo(
            page=payload.page,
            limit=payload.limit,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )

