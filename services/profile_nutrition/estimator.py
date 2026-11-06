"""Ingredient-based recipe nutrition estimation engine utilizing USDA FoodData Central."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from services.profile_nutrition.repository import ProfileRepository
from services.profile_nutrition.schemas import (
    IngredientCoverage,
    NutrientValues,
    RecipeIngredientInput,
    RecipeNutritionEstimateRequest,
    RecipeNutritionEstimateResponse,
    USDAFoodPortion,
)

# Core USDA Nutrient IDs matching USDA SR Legacy
NUTRIENT_ID_CALORIES = 1008       # Energy (KCAL)
NUTRIENT_ID_FAT = 1004            # Total lipid (fat) (G)
NUTRIENT_ID_SAT_FAT = 1258        # Fatty acids, total saturated (G)
NUTRIENT_ID_CARBS = 1005          # Carbohydrate, by difference (G)
NUTRIENT_ID_SUGAR = 2000          # Sugars, Total (G)
NUTRIENT_ID_PROTEIN = 1003        # Protein (G)
NUTRIENT_ID_SODIUM = 1093         # Sodium, Na (MG)
NUTRIENT_ID_FIBER = 1079          # Fiber, total dietary (G)

CORE_NUTRIENT_IDS = [
    NUTRIENT_ID_CALORIES,
    NUTRIENT_ID_FAT,
    NUTRIENT_ID_SAT_FAT,
    NUTRIENT_ID_CARBS,
    NUTRIENT_ID_SUGAR,
    NUTRIENT_ID_PROTEIN,
    NUTRIENT_ID_SODIUM,
    NUTRIENT_ID_FIBER,
]

# Standard unit to gram conversions for mass units
MASS_UNIT_CONVERSIONS = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "oz": 28.3495,
    "ounce": 28.3495,
    "ounces": 28.3495,
    "lb": 453.592,
    "lbs": 453.592,
    "pound": 453.592,
    "pounds": 453.592,
}

DISCLAIMER_ESTIMATE = (
    "Nutritional values are mathematical estimates based on USDA ingredient approximations and may vary. "
    "Calculations are provided strictly for educational and culinary planning purposes without clinical warranty."
)


def resolve_gram_weight(
    quantity: Optional[float],
    unit: Optional[str],
    quantity_g: Optional[float],
    portions: List[USDAFoodPortion],
) -> Optional[float]:
    """Resolve the ingredient quantity into gram weight using explicit weight or household portion tables."""
    if quantity_g is not None and quantity_g > 0:
        return float(quantity_g)

    if quantity is None or quantity <= 0:
        return None

    clean_unit = unit.strip().lower() if unit else None

    # Check direct mass unit conversion
    if clean_unit and clean_unit in MASS_UNIT_CONVERSIONS:
        return float(quantity * MASS_UNIT_CONVERSIONS[clean_unit])

    # Check USDA household portion mappings
    if clean_unit and portions:
        for p in portions:
            desc = (p.portion_description or "").lower()
            mod = (p.modifier or "").lower()
            if clean_unit in desc or clean_unit in mod:
                portion_amount = p.amount if p.amount and p.amount > 0 else 1.0
                return float((quantity / portion_amount) * p.gram_weight)

    return None


def estimate_recipe_nutrition(
    request: RecipeNutritionEstimateRequest,
    repo: ProfileRepository,
) -> RecipeNutritionEstimateResponse:
    """Calculate aggregated nutritional totals and per-serving metrics for recipe ingredients."""
    total_count = len(request.ingredients)
    if total_count == 0:
        return RecipeNutritionEstimateResponse(
            status="uncalculated",
            ingredient_coverage=IngredientCoverage(
                mapped_count=0, total_count=0, coverage_pct=0.0
            ),
            servings=request.servings,
            totals=None,
            per_serving=None,
            unmapped_ingredients=[],
            provenance_note="No ingredients provided for estimation.",
            disclaimer=DISCLAIMER_ESTIMATE,
        )

    # 1. Resolve FDC IDs for all ingredients
    resolved_ingredients: List[Tuple[RecipeIngredientInput, Optional[int]]] = []
    fdc_ids_to_fetch: Set[int] = set()

    for ing in request.ingredients:
        target_fdc = ing.fdc_id
        if not target_fdc:
            if ing.canonical_name:
                target_fdc = repo.find_fdc_id_by_name(ing.canonical_name)
            if not target_fdc and ing.raw_text:
                target_fdc = repo.find_fdc_id_by_name(ing.raw_text)

        resolved_ingredients.append((ing, target_fdc))
        if target_fdc:
            fdc_ids_to_fetch.add(target_fdc)

    # 2. Batch load nutrients and portions for all resolved foods
    food_nutrients = repo.batch_get_nutrients(list(fdc_ids_to_fetch), CORE_NUTRIENT_IDS)
    food_portions = repo.batch_get_portions(list(fdc_ids_to_fetch))

    # 3. Calculate nutrients for each mapped ingredient
    running_totals: Dict[int, float] = {nid: 0.0 for nid in CORE_NUTRIENT_IDS}
    mapped_count = 0
    mapped_fdc_ids: List[int] = []
    unmapped_ingredients: List[str] = []

    for ing, fdc_id in resolved_ingredients:
        if not fdc_id or fdc_id not in food_nutrients:
            unmapped_ingredients.append(ing.raw_text)
            continue

        portions = food_portions.get(fdc_id, [])
        gram_weight = resolve_gram_weight(
            quantity=ing.quantity,
            unit=ing.unit,
            quantity_g=ing.quantity_g,
            portions=portions,
        )

        if gram_weight is None or gram_weight <= 0:
            unmapped_ingredients.append(ing.raw_text)
            continue

        # Ingredient successfully mapped with weight
        mapped_count += 1
        mapped_fdc_ids.append(fdc_id)
        factor = gram_weight / 100.0
        nutrients_per_100g = food_nutrients[fdc_id]

        for nid in CORE_NUTRIENT_IDS:
            amt = nutrients_per_100g.get(nid)
            if amt is not None:
                running_totals[nid] += factor * amt

    # 4. Determine coverage and confidence status
    coverage_pct = round((mapped_count * 100.0) / total_count, 1)

    if coverage_pct >= 80.0:
        status_category = "calculated"
    elif coverage_pct > 0.0:
        status_category = "partial"
    else:
        status_category = "uncalculated"

    # 5. Format totals and per-serving numbers
    totals: Optional[NutrientValues] = None
    per_serving: Optional[NutrientValues] = None
    servings = max(1, request.servings)

    if mapped_count > 0:
        totals = NutrientValues(
            calories_kcal=round(running_totals[NUTRIENT_ID_CALORIES], 1)
            if running_totals[NUTRIENT_ID_CALORIES] > 0
            else None,
            total_fat_g=round(running_totals[NUTRIENT_ID_FAT], 1)
            if running_totals[NUTRIENT_ID_FAT] > 0
            else None,
            saturated_fat_g=round(running_totals[NUTRIENT_ID_SAT_FAT], 1)
            if running_totals[NUTRIENT_ID_SAT_FAT] > 0
            else None,
            carbohydrates_g=round(running_totals[NUTRIENT_ID_CARBS], 1)
            if running_totals[NUTRIENT_ID_CARBS] > 0
            else None,
            sugar_g=round(running_totals[NUTRIENT_ID_SUGAR], 1)
            if running_totals[NUTRIENT_ID_SUGAR] > 0
            else None,
            protein_g=round(running_totals[NUTRIENT_ID_PROTEIN], 1)
            if running_totals[NUTRIENT_ID_PROTEIN] > 0
            else None,
            sodium_mg=round(running_totals[NUTRIENT_ID_SODIUM], 1)
            if running_totals[NUTRIENT_ID_SODIUM] > 0
            else None,
            fiber_g=round(running_totals[NUTRIENT_ID_FIBER], 1)
            if running_totals[NUTRIENT_ID_FIBER] > 0
            else None,
        )

        per_serving = NutrientValues(
            calories_kcal=round(running_totals[NUTRIENT_ID_CALORIES] / servings, 1)
            if running_totals[NUTRIENT_ID_CALORIES] > 0
            else None,
            total_fat_g=round(running_totals[NUTRIENT_ID_FAT] / servings, 1)
            if running_totals[NUTRIENT_ID_FAT] > 0
            else None,
            saturated_fat_g=round(running_totals[NUTRIENT_ID_SAT_FAT] / servings, 1)
            if running_totals[NUTRIENT_ID_SAT_FAT] > 0
            else None,
            carbohydrates_g=round(running_totals[NUTRIENT_ID_CARBS] / servings, 1)
            if running_totals[NUTRIENT_ID_CARBS] > 0
            else None,
            sugar_g=round(running_totals[NUTRIENT_ID_SUGAR] / servings, 1)
            if running_totals[NUTRIENT_ID_SUGAR] > 0
            else None,
            protein_g=round(running_totals[NUTRIENT_ID_PROTEIN] / servings, 1)
            if running_totals[NUTRIENT_ID_PROTEIN] > 0
            else None,
            sodium_mg=round(running_totals[NUTRIENT_ID_SODIUM] / servings, 1)
            if running_totals[NUTRIENT_ID_SODIUM] > 0
            else None,
            fiber_g=round(running_totals[NUTRIENT_ID_FIBER] / servings, 1)
            if running_totals[NUTRIENT_ID_FIBER] > 0
            else None,
        )

    # 6. Provenance note
    if mapped_fdc_ids:
        unique_fdcs = sorted(set(mapped_fdc_ids))
        provenance = (
            f"Aggregated from USDA FoodData Central SR Legacy items ({', '.join(str(f) for f in unique_fdcs)})."
        )
    else:
        provenance = "No ingredients could be reliably mapped to USDA FoodData Central items."

    return RecipeNutritionEstimateResponse(
        status=status_category,
        ingredient_coverage=IngredientCoverage(
            mapped_count=mapped_count,
            total_count=total_count,
            coverage_pct=coverage_pct,
        ),
        servings=servings,
        totals=totals,
        per_serving=per_serving,
        unmapped_ingredients=unmapped_ingredients,
        provenance_note=provenance,
        disclaimer=DISCLAIMER_ESTIMATE,
    )

