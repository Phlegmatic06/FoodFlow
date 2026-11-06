"""Automated meal plan schedule generator proposal engine."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from services.recommendation_planner.client import ProfileServiceClient, RecipeServiceClient
from services.recommendation_planner.config import settings
from services.recommendation_planner.schemas import (
    GeneratedDayPlan,
    GeneratedMealPlanResponse,
    GeneratedSlotProposal,
    GenerateMealPlanRequest,
)

logger = logging.getLogger(f"foodflow.{settings.service_name}")


def generate_meal_plan_proposal(
    request: GenerateMealPlanRequest,
    recipe_client: RecipeServiceClient,
    profile_client: ProfileServiceClient,
) -> GeneratedMealPlanResponse:
    """
    Generate an unpersisted multi-day meal plan proposal.

    Orchestration:
    1. Queries Recipe Service for candidate recipes matching filters (cuisine, diet, max_time).
    2. Maps candidate recipes to day slots.
    3. Retrieves caloric estimates from Profile Service or Recipe Service metadata.
    4. Enforces non-fabrication: uncalculated calories remain null.
    """
    total_slots_needed = request.days * len(request.slots)

    # 1. Fetch candidate recipes from Recipe Service
    search_res = recipe_client.search_recipes(
        cuisine=request.cuisine_preference,
        diet=request.diet_preference,
        max_time=request.max_time_per_recipe,
        limit=min(48, max(24, total_slots_needed * 2)),
    )
    candidates: List[Dict[str, Any]] = search_res.get("items", [])

    # If filters yielded too few recipes, supplement with general search
    if len(candidates) < total_slots_needed:
        fallback_res = recipe_client.search_recipes(
            limit=48,
        )
        existing_ids = {c["id"] for c in candidates}
        for item in fallback_res.get("items", []):
            if item["id"] not in existing_ids:
                candidates.append(item)
                existing_ids.add(item["id"])

    notes: List[str] = []
    if request.diet_preference:
        notes.append(f"Dietary preference applied: {request.diet_preference}")
    if request.cuisine_preference:
        notes.append(f"Cuisine preference applied: {request.cuisine_preference}")
    if request.target_calories_kcal:
        notes.append(f"Target daily calories: {request.target_calories_kcal} kcal")

    day_plans: List[GeneratedDayPlan] = []
    cand_idx = 0
    num_candidates = len(candidates)

    for day_i in range(request.days):
        slot_proposals: List[GeneratedSlotProposal] = []
        day_cal_sum = 0.0
        has_cal_data = False

        for slot_type in request.slots:
            if num_candidates > 0:
                recipe = candidates[cand_idx % num_candidates]
                cand_idx += 1
                recipe_id = recipe["id"]
                title = recipe["title"]
                total_time = recipe.get("total_time_minutes")

                # Try to get calories
                est_cals: Optional[float] = None
                raw_nut = recipe.get("nutrition")
                if raw_nut and raw_nut.get("calories") is not None:
                    try:
                        est_cals = float(raw_nut["calories"])
                    except (ValueError, TypeError):
                        pass

                if est_cals is None:
                    # Query profile service cached estimate
                    cached = profile_client.get_cached_recipe_nutrition(recipe_id)
                    if cached and cached.get("calories_kcal") is not None:
                        est_cals = float(cached["calories_kcal"])

                if est_cals is not None and est_cals > 0:
                    day_cal_sum += est_cals
                    has_cal_data = True

                slot_proposals.append(
                    GeneratedSlotProposal(
                        slot_type=slot_type,
                        recipe_id=recipe_id,
                        title=title,
                        total_time_minutes=total_time,
                        estimated_calories_kcal=est_cals,
                    )
                )
            else:
                slot_proposals.append(
                    GeneratedSlotProposal(
                        slot_type=slot_type,
                        recipe_id="rcp_foodcom_default",
                        title=f"{slot_type.capitalize()} Recipe",
                        total_time_minutes=30,
                        estimated_calories_kcal=None,
                    )
                )

        day_total_cal = round(day_cal_sum, 1) if has_cal_data else None

        day_plans.append(
            GeneratedDayPlan(
                day_index=day_i,
                slots=slot_proposals,
                day_total_calories_kcal=day_total_cal,
            )
        )

    return GeneratedMealPlanResponse(
        target_calories_kcal=request.target_calories_kcal,
        days=day_plans,
        notes=notes,
    )
