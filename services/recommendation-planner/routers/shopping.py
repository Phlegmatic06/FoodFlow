"""Consolidated grocery shopping list endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Path, status

from services.recommendation_planner.categorizer import aggregate_shopping_ingredients
from services.recommendation_planner.client import RecipeServiceClient, UpstreamServiceUnavailableError
from services.recommendation_planner.dependencies import (
    get_recipe_client,
    get_repository,
    get_required_guest_session,
)
from services.recommendation_planner.repository import PlannerRepository
from services.recommendation_planner.schemas import (
    ShoppingListItem,
    ShoppingListResponse,
    UpdateShoppingItemRequest,
)

router = APIRouter(prefix="/api/v1/meal-plans", tags=["Shopping Lists"])


@router.get(
    "/{plan_id}/shopping-list",
    response_model=ShoppingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get or generate consolidated shopping list",
    description=(
        "Returns the consolidated grocery shopping list for a meal plan, grouped by aisle category. "
        "Generates list from recipe ingredients on first request, or returns previously stored list."
    ),
)
def get_shopping_list(
    plan_id: str = Path(..., description="UUID meal plan identifier"),
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
    recipe_client: RecipeServiceClient = Depends(get_recipe_client),
) -> ShoppingListResponse:
    """Retrieve or generate consolidated grocery list for meal plan."""
    try:
        uuid.UUID(plan_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Meal plan '{plan_id}' was not found",
                "details": [],
            },
        )

    # 1. Verify plan exists and is owned by session
    plan = repo.get_meal_plan(plan_id, guest_session_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Meal plan '{plan_id}' was not found or is not owned by this session",
                "details": [],
            },
        )

    # 2. Check if shopping list already exists
    existing = repo.get_or_create_shopping_list(plan_id, guest_session_id, items_to_create=None)
    if existing:
        return existing

    # 3. Generate from meal plan recipe ingredients
    recipe_ids = list({s.recipe_id for s in plan.slots})
    raw_ingredients: List[Dict[str, Any]] = []

    if recipe_ids:
        try:
            batch_res = recipe_client.batch_get_recipes(recipe_ids)
            for rec in batch_res.get("recipes", []):
                for ing in rec.get("ingredients", []):
                    raw_ingredients.append(ing)
        except UpstreamServiceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "SERVICE_UNAVAILABLE",
                    "message": f"Failed to retrieve recipe ingredients for shopping list: {exc.message}",
                    "details": [],
                },
            ) from exc

    # Consolidate and categorize
    aggregated = aggregate_shopping_ingredients(raw_ingredients)

    # Persist and return
    created = repo.get_or_create_shopping_list(plan_id, guest_session_id, items_to_create=aggregated)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Failed to initialize shopping list for plan '{plan_id}'",
                "details": [],
            },
        )
    return created


@router.patch(
    "/{plan_id}/shopping-list/items/{item_id}",
    response_model=ShoppingListItem,
    status_code=status.HTTP_200_OK,
    summary="Toggle shopping item checked status",
    description="Updates procurement check state of an item on the shopping list.",
)
def update_shopping_list_item(
    payload: UpdateShoppingItemRequest,
    plan_id: str = Path(..., description="UUID meal plan identifier"),
    item_id: int = Path(..., description="Item integer identifier"),
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
) -> ShoppingListItem:
    """Toggle procurement check state for a shopping list item."""
    try:
        uuid.UUID(plan_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Meal plan '{plan_id}' was not found",
                "details": [],
            },
        )

    updated_item = repo.update_shopping_list_item(
        plan_id=plan_id,
        item_id=item_id,
        guest_session_id=guest_session_id,
        checked=payload.checked,
    )
    if not updated_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Shopping list item {item_id} was not found on meal plan '{plan_id}'",
                "details": [],
            },
        )
    return updated_item

