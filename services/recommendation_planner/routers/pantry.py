"""Pantry inventory management and pantry-to-recipe overlap matching endpoints."""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from services.recommendation_planner.client import (
    RecipeServiceClient,
    UpstreamServiceUnavailableError,
)
from services.recommendation_planner.dependencies import (
    get_optional_guest_session,
    get_recipe_client,
    get_repository,
    get_required_guest_session,
)
from services.recommendation_planner.matcher import match_pantry_recipes
from services.recommendation_planner.repository import PlannerRepository
from services.recommendation_planner.schemas import (
    PantryInventoryResponse,
    PantryMatchRequest,
    PantryMatchResponse,
    UpdatePantryItemInput,
    UpdatePantryRequest,
)

router = APIRouter(prefix="/api/v1/pantry", tags=["Pantry Inventory", "Pantry Matching"])


@router.get(
    "",
    response_model=PantryInventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve guest pantry inventory",
    description="Returns stored pantry items for the current session.",
)
def get_pantry(
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
) -> PantryInventoryResponse:
    """List current pantry inventory for guest session."""
    items = repo.get_pantry_items(guest_session_id)
    return PantryInventoryResponse(items=items, total_count=len(items))


@router.put(
    "",
    response_model=PantryInventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Replace entire guest pantry inventory",
    description=(
        "Overwrites full pantry contents for the current session. "
        "Preserves original raw ingredient strings. An empty items array clears the inventory."
    ),
)
def update_pantry(
    payload: UpdatePantryRequest,
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
    recipe_client: RecipeServiceClient = Depends(get_recipe_client),
) -> PantryInventoryResponse:
    """Replace pantry inventory items."""
    processed_items: List[UpdatePantryItemInput] = []

    # Attempt normalization for items missing canonical_ingredient_id
    raw_texts_to_normalize: List[str] = [
        it.raw_name.strip() for it in payload.items if it.canonical_ingredient_id is None and it.raw_name.strip()
    ]

    canonical_map = {}
    if raw_texts_to_normalize:
        try:
            norm_res = recipe_client.normalize_ingredients(raw_texts_to_normalize)
            for item in norm_res.get("results", norm_res.get("normalized", [])):
                raw = item.get("raw_input", item.get("raw_text"))
                cid = item.get("canonical_id")
                if raw and cid:
                    canonical_map[raw.lower()] = cid
        except Exception:
            # If normalization service is unreachable or empty, preserve raw string without failure
            pass

    for it in payload.items:
        clean_name = it.raw_name.strip()
        if not clean_name:
            continue
        canon_id = it.canonical_ingredient_id or canonical_map.get(clean_name.lower())
        processed_items.append(
            UpdatePantryItemInput(
                raw_name=clean_name,
                canonical_ingredient_id=canon_id,
            )
        )

    updated_items = repo.replace_pantry_items(guest_session_id, processed_items)
    return PantryInventoryResponse(items=updated_items, total_count=len(updated_items))


@router.post(
    "/match",
    response_model=PantryMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Find recipes matching pantry ingredients",
    description=(
        "Calculates ingredient overlap against the recipe catalogue. "
        "Uses ingredients supplied in request body, or falls back to saved guest pantry if omitted. "
        "Reports deterministic match percentages and distinguishes matched from missing items."
    ),
)
def match_pantry(
    payload: Optional[PantryMatchRequest] = None,
    guest_session_id: Optional[str] = Depends(get_optional_guest_session),
    repo: PlannerRepository = Depends(get_repository),
    recipe_client: RecipeServiceClient = Depends(get_recipe_client),
) -> PantryMatchResponse:
    """Match pantry ingredients against recipe catalogue."""
    req = payload or PantryMatchRequest()

    # Determine ingredients list
    ingredient_strings: List[str] = []
    if req.ingredients and len(req.ingredients) > 0:
        ingredient_strings = [s for s in req.ingredients if s and s.strip()]
    elif guest_session_id:
        pantry_items = repo.get_pantry_items(guest_session_id)
        ingredient_strings = [item.raw_name for item in pantry_items if item.raw_name.strip()]

    if not ingredient_strings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "No pantry ingredients provided for matching",
                "details": [
                    {
                        "field": "ingredients",
                        "issue": "Provide ingredients array or an active guest session with stored pantry items",
                    }
                ],
            },
        )

    try:
        return match_pantry_recipes(req, ingredient_strings, recipe_client)
    except UpstreamServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": str(exc.message),
                "details": [],
            },
        ) from exc

