"""Meal plan scheduling, proposal generation, persistence, and cooking progress endpoints."""

from __future__ import annotations

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from services.recommendation_planner.client import (
    ProfileServiceClient,
    RecipeServiceClient,
    UpstreamServiceUnavailableError,
)
from services.recommendation_planner.dependencies import (
    get_profile_client,
    get_recipe_client,
    get_repository,
    get_required_guest_session,
)
from services.recommendation_planner.generator import generate_meal_plan_proposal
from services.recommendation_planner.repository import PlannerRepository
from services.recommendation_planner.schemas import (
    GeneratedMealPlanResponse,
    GenerateMealPlanRequest,
    MealPlanDetail,
    SavedMealPlanSummary,
    SaveMealPlanRequest,
    UpdateCookingProgressRequest,
    UpdateProgressResponse,
)

router = APIRouter(prefix="/api/v1/meal-plans", tags=["Meal Planning"])


@router.post(
    "/generate",
    response_model=GeneratedMealPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Auto-generate a structured meal plan",
    description=(
        "Proposes an unpersisted multi-day meal schedule matching requested slots, "
        "dietary restrictions, and caloric targets. Queries Recipe and Profile services."
    ),
)
def generate_meal_plan(
    payload: GenerateMealPlanRequest,
    recipe_client: RecipeServiceClient = Depends(get_recipe_client),
    profile_client: ProfileServiceClient = Depends(get_profile_client),
) -> GeneratedMealPlanResponse:
    """Generate structured meal plan proposal."""
    try:
        return generate_meal_plan_proposal(payload, recipe_client, profile_client)
    except UpstreamServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": str(exc.message),
                "details": [],
            },
        ) from exc


@router.post(
    "",
    response_model=SavedMealPlanSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Save a meal plan to the guest session",
    description=(
        "Persists a multi-day meal plan with scheduled recipe slots. "
        "Validates that all referenced recipe identifiers exist in the catalogue."
    ),
)
def save_meal_plan(
    payload: SaveMealPlanRequest,
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
    recipe_client: RecipeServiceClient = Depends(get_recipe_client),
) -> SavedMealPlanSummary:
    """Persist proposed or custom meal plan."""
    # Validate referenced recipe IDs exist in Recipe Service
    recipe_ids = list({s.recipe_id for s in payload.slots})
    try:
        batch_res = recipe_client.batch_get_recipes(recipe_ids)
    except UpstreamServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": f"Recipe verification failed: {exc.message}",
                "details": [],
            },
        ) from exc

    missing_ids = batch_res.get("missing_ids", [])
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"One or more referenced recipes do not exist: {', '.join(missing_ids)}",
                "details": [
                    {
                        "field": "slots",
                        "issue": f"Recipe '{rid}' was not found in recipe catalogue",
                    }
                    for rid in missing_ids
                ],
            },
        )

    return repo.create_meal_plan(guest_session_id, payload)


@router.get(
    "/{plan_id}",
    response_model=MealPlanDetail,
    status_code=status.HTTP_200_OK,
    summary="Retrieve saved meal plan details",
    description="Returns complete schedule, slots, and cooking execution progress for an owned plan.",
)
def get_meal_plan(
    plan_id: str = Path(..., description="UUID meal plan identifier"),
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
) -> MealPlanDetail:
    """Retrieve full details of an owned meal plan."""
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
    return plan


@router.put(
    "/{plan_id}",
    response_model=MealPlanDetail,
    status_code=status.HTTP_200_OK,
    summary="Replace meal plan schedule",
    description="Replaces slots, days, and target calories for an existing meal plan.",
)
def update_meal_plan(
    payload: SaveMealPlanRequest,
    plan_id: str = Path(..., description="UUID meal plan identifier"),
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
    recipe_client: RecipeServiceClient = Depends(get_recipe_client),
) -> MealPlanDetail:
    """Replace slots of an existing meal plan."""
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

    # Validate recipes
    recipe_ids = list({s.recipe_id for s in payload.slots})
    try:
        batch_res = recipe_client.batch_get_recipes(recipe_ids)
    except UpstreamServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": f"Recipe verification failed: {exc.message}",
                "details": [],
            },
        ) from exc

    missing_ids = batch_res.get("missing_ids", [])
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"One or more referenced recipes do not exist: {', '.join(missing_ids)}",
                "details": [
                    {
                        "field": "slots",
                        "issue": f"Recipe '{rid}' was not found in recipe catalogue",
                    }
                    for rid in missing_ids
                ],
            },
        )

    updated = repo.update_meal_plan(plan_id, guest_session_id, payload)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Meal plan '{plan_id}' was not found or is not owned by this session",
                "details": [],
            },
        )
    return updated


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete meal plan",
    description="Deletes meal plan, scheduled slots, and associated shopping lists.",
)
def delete_meal_plan(
    plan_id: str = Path(..., description="UUID meal plan identifier"),
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
) -> Response:
    """Delete an owned meal plan."""
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

    deleted = repo.delete_meal_plan(plan_id, guest_session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Meal plan '{plan_id}' was not found or is not owned by this session",
                "details": [],
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{plan_id}/progress",
    response_model=UpdateProgressResponse,
    status_code=status.HTTP_200_OK,
    summary="Update cooking status of planned meal slots",
    description="Batch records execution state (pending, cooked, skipped) for slots in an owned plan.",
)
def update_cooking_progress(
    payload: UpdateCookingProgressRequest,
    plan_id: str = Path(..., description="UUID meal plan identifier"),
    guest_session_id: str = Depends(get_required_guest_session),
    repo: PlannerRepository = Depends(get_repository),
) -> UpdateProgressResponse:
    """Update cooking progress states."""
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

    updated_count = repo.update_slot_cooking_progress(plan_id, guest_session_id, payload.updates)
    if updated_count is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "RESOURCE_NOT_FOUND",
                "message": f"Meal plan '{plan_id}' or specified slot was not found or not owned by session",
                "details": [],
            },
        )

    return UpdateProgressResponse(updated_count=updated_count, plan_id=plan_id)

