"""Pantry-to-recipe overlap matching and recommendation engine."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional
from services.recommendation_planner.client import RecipeServiceClient
from services.recommendation_planner.config import settings
from services.recommendation_planner.schemas import (
    PaginationInfo,
    PantryMatchRequest,
    PantryMatchResponse,
    PantryMatchResultItem,
)

logger = logging.getLogger(f"foodflow.{settings.service_name}")

# Universal basic staples to optionally exclude from match denominator
PANTRY_STAPLES = {"water", "salt", "black pepper", "pepper"}


def match_pantry_recipes(
    request: PantryMatchRequest,
    ingredient_strings: List[str],
    recipe_client: RecipeServiceClient,
) -> PantryMatchResponse:
    """
    Orchestrate pantry matching using Recipe Service REST APIs.

    Follows strict evidence-based principles:
    - Normalizes ingredients via Recipe Service.
    - If canonical dictionary is empty or no valid canonical mappings exist,
      returns an honest empty recommendation response without fabricating matches.
    - If valid canonical IDs exist, queries candidate recipes and calculates precise overlap.
    """
    clean_ingredients = [s.strip() for s in ingredient_strings if s and s.strip()]
    if not clean_ingredients:
        return PantryMatchResponse(
            matches=[],
            pagination=PaginationInfo(
                page=request.page,
                limit=request.limit,
                total_items=0,
                total_pages=0,
            ),
        )

    # 1. Normalize ingredient strings via Recipe Service
    try:
        norm_result = recipe_client.normalize_ingredients(clean_ingredients)
    except Exception as exc:
        logger.warning("Failed to normalize ingredients via Recipe Service: %s", exc)
        raise

    normalized_items: List[Dict[str, Any]] = norm_result.get("results", norm_result.get("normalized", []))
    valid_canonical_ids: List[int] = [
        it["canonical_id"] for it in normalized_items if it.get("canonical_id") is not None
    ]

    # Without verified canonical mappings, we must not fabricate matches or fall back to fuzzy guessing.
    if not valid_canonical_ids:
        logger.info(
            "Ingredient normalization yielded zero canonical matches. "
            "Returning empty match result per specification."
        )
        return PantryMatchResponse(
            matches=[],
            pagination=PaginationInfo(
                page=request.page,
                limit=request.limit,
                total_items=0,
                total_pages=0,
            ),
        )

    # 2. Query candidate recipes matching canonical IDs
    min_ratio = request.min_match_pct / 100.0
    try:
        cand_result = recipe_client.search_by_ingredients(
            ingredient_ids=valid_canonical_ids,
            min_match_ratio=min_ratio,
            limit=request.limit,
        )
    except Exception as exc:
        logger.warning("Failed to search recipes by ingredients: %s", exc)
        raise

    raw_matches = cand_result.get("data", cand_result.get("matches", []))
    total_candidates = cand_result.get("pagination", {}).get("total_items", cand_result.get("total", len(raw_matches)))

    if not raw_matches:
        return PantryMatchResponse(
            matches=[],
            pagination=PaginationInfo(
                page=request.page,
                limit=request.limit,
                total_items=total_candidates,
                total_pages=math.ceil(total_candidates / request.limit) if total_candidates > 0 else 0,
            ),
        )

    # 3. Batch fetch recipe details for candidate recipes
    recipe_ids = [m["recipe_id"] for m in raw_matches]
    batch_data = recipe_client.batch_get_recipes(recipe_ids)
    recipes_by_id = {r["id"]: r for r in batch_data.get("recipes", [])}

    # 4. Compute ingredient overlap for each candidate recipe
    canonical_id_set = set(valid_canonical_ids)
    pantry_raw_names_lower = {s.lower() for s in clean_ingredients}

    matched_results: List[PantryMatchResultItem] = []
    for m in raw_matches:
        rid = m["recipe_id"]
        recipe_rec = recipes_by_id.get(rid)
        if not recipe_rec:
            continue

        recipe_ingredients = recipe_rec.get("ingredients", [])
        matched_ing: List[str] = []
        missing_ing: List[str] = []

        for ing in recipe_ingredients:
            ing_raw = (
                ing.get("raw_text")
                or ing.get("canonical_name")
                or ing.get("name")
                or "ingredient"
            )
            ing_canon_id = (
                ing.get("canonical_ingredient_id")
                or ing.get("canonical_id")
            )
            ing_name_lower = (
                ing.get("canonical_name")
                or ing.get("name")
                or ""
            ).strip().lower()

            if request.exclude_pantry_staples and ing_name_lower in PANTRY_STAPLES:
                continue

            # Overlap check strictly via verified canonical ID
            is_matched = bool(ing_canon_id is not None and ing_canon_id in canonical_id_set)

            if is_matched:
                matched_ing.append(ing_raw)
            else:
                missing_ing.append(ing_raw)

        total_tracked = len(matched_ing) + len(missing_ing)
        if total_tracked == 0:
            pct = 0.0
        else:
            pct = round((len(matched_ing) * 100.0) / total_tracked, 1)

        matched_results.append(
            PantryMatchResultItem(
                recipe_id=rid,
                title=recipe_rec.get("title", "Untitled Recipe"),
                match_pct=pct,
                matched_ingredients=matched_ing,
                missing_ingredients=missing_ing,
                total_recipe_ingredients=len(recipe_ingredients),
                total_time_minutes=recipe_rec.get("total_time_minutes"),
                rating_average=recipe_rec.get("rating_average"),
            )
        )

    # Sort descending by match_pct
    matched_results.sort(key=lambda x: x.match_pct, reverse=True)

    return PantryMatchResponse(
        matches=matched_results,
        pagination=PaginationInfo(
            page=request.page,
            limit=request.limit,
            total_items=total_candidates,
            total_pages=math.ceil(total_candidates / request.limit) if total_candidates > 0 else 0,
        ),
    )
