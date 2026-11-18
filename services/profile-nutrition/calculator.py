"""Nutritional and physical biometrics calculation engine."""

from __future__ import annotations

from typing import Optional, Tuple

from services.profile_nutrition.schemas import (
    BiometricsCalculationRequest,
    BiometricsCalculationResponse,
    MacroRangePercentage,
    MacroRangesPercent,
    MacroTargets,
)

# Activity multipliers matching official WHO/FAO/Mifflin-St Jeor guidelines
ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "lightly_active": 1.375,
    "moderately_active": 1.55,
    "very_active": 1.725,
    "extra_active": 1.9,
}

# Caloric goal adjustments (conservative sustainable shifts)
GOAL_ADJUSTMENTS = {
    "maintain": 0,
    "lose": -400,
    "gain": 400,
}

# Authoritative NutriPod default macro distribution
# Invariant: DEFAULT_PROTEIN_PCT + DEFAULT_CARBS_PCT + DEFAULT_FAT_PCT == 100.0
DEFAULT_PROTEIN_PCT = 20.0
DEFAULT_CARBS_PCT = 50.0
DEFAULT_FAT_PCT = 30.0

# Standard Atwater general energy factors (kcal per gram)
KCAL_PER_G_PROTEIN = 4.0
KCAL_PER_G_CARBS = 4.0
KCAL_PER_G_FAT = 9.0

# Minimum safe baseline daily caloric intake floor (kcal/day)
MIN_CALORIE_FLOOR_KCAL = 1200

DISCLAIMER_TEXT = (
    "These calculated estimates are provided strictly for educational and culinary planning purposes. "
    "They do not constitute medical diagnosis, clinical advice, or individualized nutritional prescription. "
    "Consult a licensed medical provider or registered dietitian before making significant dietary changes."
)


def calculate_macro_targets(target_calories_kcal: int) -> MacroTargets:
    """Calculate macronutrient target grams from daily caloric target using 20/50/30 distribution.

    Formulas:
        protein_g = round((target_calories_kcal * 0.20) / 4.0)
        carbs_g   = round((target_calories_kcal * 0.50) / 4.0)
        fat_g     = round((target_calories_kcal * 0.30) / 9.0)

    Validation Invariant:
        DEFAULT_PROTEIN_PCT + DEFAULT_CARBS_PCT + DEFAULT_FAT_PCT == 100.0
    """
    total_pct = DEFAULT_PROTEIN_PCT + DEFAULT_CARBS_PCT + DEFAULT_FAT_PCT
    if abs(total_pct - 100.0) > 1e-6:
        raise ValueError(f"Macronutrient target percentages must sum to 100.0%, got {total_pct}%")

    protein_g = round((target_calories_kcal * (DEFAULT_PROTEIN_PCT / 100.0)) / KCAL_PER_G_PROTEIN)
    carbs_g = round((target_calories_kcal * (DEFAULT_CARBS_PCT / 100.0)) / KCAL_PER_G_CARBS)
    fat_g = round((target_calories_kcal * (DEFAULT_FAT_PCT / 100.0)) / KCAL_PER_G_FAT)

    return MacroTargets(
        protein_g=protein_g,
        carbohydrates_g=carbs_g,
        fat_g=fat_g,
    )


def calculate_bmi(weight_kg: float, height_cm: float) -> Tuple[float, str]:
    """Calculate Body Mass Index (BMI) and assign WHO classification category."""
    height_m = height_cm / 100.0
    bmi = round(weight_kg / (height_m * height_m), 2)

    if bmi < 18.5:
        category = "underweight"
    elif bmi < 25.0:
        category = "normal_weight"
    elif bmi < 30.0:
        category = "overweight"
    elif bmi < 35.0:
        category = "obesity_class_1"
    elif bmi < 40.0:
        category = "obesity_class_2"
    else:
        category = "obesity_class_3"

    return bmi, category


def calculate_bmr(
    weight_kg: float, height_cm: float, age_years: int, sex: Optional[str]
) -> Optional[float]:
    """Calculate Basal Metabolic Rate using the Mifflin-St Jeor (1990) equation."""
    if not sex:
        return None

    if sex == "male":
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age_years) + 5.0
    elif sex == "female":
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age_years) - 161.0
    else:
        return None

    return round(bmr, 1)


def calculate_biometrics(request: BiometricsCalculationRequest) -> BiometricsCalculationResponse:
    """Execute complete biometrics calculation pipeline."""
    bmi, bmi_category = calculate_bmi(request.weight_kg, request.height_cm)

    bmr = calculate_bmr(
        weight_kg=request.weight_kg,
        height_cm=request.height_cm,
        age_years=request.age_years,
        sex=request.sex_for_equation,
    )

    if bmr is None:
        # Sex was omitted; return BMI only without fabricated metabolic metrics
        return BiometricsCalculationResponse(
            bmi=bmi,
            bmi_category=bmi_category,
            bmr_kcal=None,
            tdee_kcal=None,
            target_calories_kcal=None,
            formula="mifflin_st_jeor",
            activity_multiplier=None,
            goal=request.goal,
            goal_adjustment_kcal=None,
            macro_targets_grams=None,
            macro_ranges_percent=MacroRangesPercent(),
            caveats=[
                "Biological sex was omitted; BMR, TDEE, and calorie targets are not calculated to prevent fabricated estimates."
            ],
            disclaimer=DISCLAIMER_TEXT,
        )

    multiplier = ACTIVITY_FACTORS[request.activity_level]
    tdee = round(bmr * multiplier, 2)
    goal_adj = GOAL_ADJUSTMENTS.get(request.goal, 0)
    # Ensure minimum safe baseline calorie threshold (1200 kcal/day)
    target_calories = max(MIN_CALORIE_FLOOR_KCAL, round(tdee + goal_adj))

    macro_targets = calculate_macro_targets(target_calories)

    activity_label = request.activity_level.replace("_", " ")
    caveats = [
        "BMR calculated using the Mifflin-St Jeor equation (1990).",
        f"TDEE applies physical activity level factor {multiplier} ({activity_label}).",
        f"Macronutrient target distribution is {int(DEFAULT_PROTEIN_PCT)}% protein, {int(DEFAULT_CARBS_PCT)}% carbohydrates, and {int(DEFAULT_FAT_PCT)}% fat based on NutriPod default macro distribution.",
    ]
    if request.age_years < 18:
        caveats.append(
            "Mifflin-St Jeor and adult NutriPod default macro distribution targets are calibrated for adult populations (18+); "
            "pediatric metrics should be evaluated with a qualified pediatric health professional."
        )

    return BiometricsCalculationResponse(
        bmi=bmi,
        bmi_category=bmi_category,
        bmr_kcal=bmr,
        tdee_kcal=tdee,
        target_calories_kcal=target_calories,
        formula="mifflin_st_jeor",
        activity_multiplier=multiplier,
        goal=request.goal,
        goal_adjustment_kcal=goal_adj,
        macro_targets_grams=macro_targets,
        macro_ranges_percent=MacroRangesPercent(
            protein=MacroRangePercentage(min_pct=10, max_pct=35),
            carbohydrates=MacroRangePercentage(min_pct=45, max_pct=65),
            fat=MacroRangePercentage(min_pct=20, max_pct=35),
        ),
        caveats=caveats,
        disclaimer=DISCLAIMER_TEXT,
    )

