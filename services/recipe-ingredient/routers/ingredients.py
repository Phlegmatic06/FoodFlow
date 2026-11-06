"""Ingredient taxonomy, normalization, and autocomplete suggestion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from services.common.database import ServiceDatabaseManager
from services.recipe_ingredient.database import get_db_manager
from services.recipe_ingredient.repository import RecipeRepository
from services.recipe_ingredient.schemas import (
    IngredientSuggestion,
    NormalizedIngredientResult,
    NormalizeIngredientsRequest,
    NormalizeIngredientsResponse,
)

router = APIRouter(prefix="/api/v1/ingredients", tags=["Ingredient Taxonomy"])


def get_repository(
    db: ServiceDatabaseManager = Depends(get_db_manager),
) -> RecipeRepository:
    """Dependency provider returning a RecipeRepository instance."""
    return RecipeRepository(db)


@router.post(
    "/normalize",
    response_model=NormalizeIngredientsResponse,
    status_code=status.HTTP_200_OK,
    summary="Normalize raw ingredient strings to canonical taxonomy",
    description=(
        "Maps free-form ingredient text to canonical ingredient entries using exact lexical "
        "matches, synonym dictionaries, and pg_trgm similarity."
    ),
)
def normalize_ingredients(
    payload: NormalizeIngredientsRequest,
    repo: RecipeRepository = Depends(get_repository),
) -> NormalizeIngredientsResponse:
    """Ingredient normalization endpoint."""
    results = repo.normalize_ingredients(payload.ingredients)
    return NormalizeIngredientsResponse(results=results)


@router.get(
    "/suggestions",
    response_model=list[IngredientSuggestion],
    status_code=status.HTTP_200_OK,
    summary="Autocomplete search for canonical ingredients",
    description="Fast prefix and trigram lookup on canonical ingredient names.",
)
def get_ingredient_suggestions(
    q: str = Query(..., min_length=1, max_length=100, description="Query string prefix or fragment"),
    limit: int = Query(10, ge=1, le=25, description="Max suggestions to return"),
    repo: RecipeRepository = Depends(get_repository),
) -> list[IngredientSuggestion]:
    """Autocomplete suggestions endpoint."""
    clean_q = q.strip()
    if not clean_q:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter 'q' must not be empty",
        )
    return repo.get_ingredient_suggestions(clean_q, limit=limit)

