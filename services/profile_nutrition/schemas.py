"""Pydantic schemas for the Profile & Nutrition Service matching OpenAPI contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PaginationInfo(BaseModel):
    """Metadata describing a paginated collection."""

    page: int = Field(..., ge=1, example=1)
    limit: int = Field(..., ge=1, le=48, example=24)
    total_items: int = Field(..., ge=0, example=142)
    total_pages: int = Field(..., ge=0, example=6)


class BiometricsCalculationRequest(BaseModel):
    """Input parameters for health biometrics calculation."""

    age_years: int = Field(..., ge=1, le=120, description="Chronological age in years", example=28)
    sex_for_equation: Optional[Literal["male", "female"]] = Field(
        None,
        description=(
            "Biological sex parameter required specifically for Mifflin-St Jeor BMR equation constants. "
            "If null or omitted, BMR and TDEE are not calculated."
        ),
        example="male",
    )
    height_cm: float = Field(
        ..., ge=50.0, le=300.0, description="Height measured in centimeters", example=182.0
    )
    weight_kg: float = Field(
        ..., ge=20.0, le=500.0, description="Weight measured in kilograms", example=80.0
    )
    activity_level: Literal[
        "sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"
    ] = Field(
        ...,
        description="Physical activity multiplier level from sedentary (1.2) to extra_active (1.9)",
        example="moderately_active",
    )
    goal: Literal["maintain", "lose", "gain"] = Field(
        default="maintain",
        description="Weight management goal: maintain (0 kcal), lose (-400 kcal), gain (+400 kcal)",
        example="maintain",
    )


class MacroTargets(BaseModel):
    """Target macronutrient distribution in grams per day and percentage split."""

    protein_g: int = Field(..., example=140)
    carbohydrates_g: int = Field(..., example=349)
    fat_g: int = Field(..., example=93)

    @property
    def protein_pct(self) -> float:
        """Recommended protein percentage of daily energy (20%)."""
        return 20.0

    @property
    def carbohydrates_pct(self) -> float:
        """Recommended carbohydrates percentage of daily energy (50%)."""
        return 50.0

    @property
    def fat_pct(self) -> float:
        """Recommended fat percentage of daily energy (30%)."""
        return 30.0


class MacroRangePercentage(BaseModel):
    """Acceptable macronutrient distribution range bounds in percentage of total daily calories."""

    min_pct: int = Field(..., example=10)
    max_pct: int = Field(..., example=35)


class MacroRangesPercent(BaseModel):
    """AMDR percentage ranges for protein, carbohydrates, and fat."""

    protein: MacroRangePercentage = Field(
        default_factory=lambda: MacroRangePercentage(min_pct=10, max_pct=35)
    )
    carbohydrates: MacroRangePercentage = Field(
        default_factory=lambda: MacroRangePercentage(min_pct=45, max_pct=65)
    )
    fat: MacroRangePercentage = Field(
        default_factory=lambda: MacroRangePercentage(min_pct=20, max_pct=35)
    )


class BiometricsCalculationResponse(BaseModel):
    """Result of physical biometrics and nutritional goal calculations."""

    bmi: float = Field(..., description="Body Mass Index (kg / m^2)", example=24.15)
    bmi_category: Literal[
        "underweight", "normal_weight", "overweight", "obesity_class_1", "obesity_class_2", "obesity_class_3"
    ] = Field(..., example="normal_weight")
    bmr_kcal: Optional[float] = Field(
        None, description="Basal Metabolic Rate in kcal/day. NULL if sex was omitted.", example=1802.5
    )
    tdee_kcal: Optional[float] = Field(
        None, description="Total Daily Energy Expenditure in kcal/day.", example=2793.88
    )
    target_calories_kcal: Optional[int] = Field(
        None, description="Recommended daily calorie intake adjusted for goal.", example=2794
    )
    formula: str = Field(default="mifflin_st_jeor", example="mifflin_st_jeor")
    activity_multiplier: Optional[float] = Field(None, example=1.55)
    goal: str = Field(default="maintain", example="maintain")
    goal_adjustment_kcal: Optional[int] = Field(None, example=0)
    macro_targets_grams: Optional[MacroTargets] = None
    macro_ranges_percent: MacroRangesPercent = Field(default_factory=MacroRangesPercent)
    caveats: List[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default=(
            "These calculated estimates are provided strictly for educational and culinary planning purposes. "
            "They do not constitute medical diagnosis, clinical advice, or individualized nutritional prescription. "
            "Consult a licensed medical provider or registered dietitian before making significant dietary changes."
        )
    )


class USDAFoodSummary(BaseModel):
    """Condensed summary of a USDA food item."""

    fdc_id: int = Field(..., description="USDA FoodData Central identifier", example=170554)
    data_type: str = Field(..., example="sr_legacy_food")
    description: str = Field(..., example="Oats, whole grain, rolled")
    food_category_id: Optional[int] = Field(None, example=20)
    publication_date: Optional[date] = Field(None, example="2019-04-01")


class PaginatedUSDAFoodSummary(BaseModel):
    """Paginated collection of USDA food items."""

    data: List[USDAFoodSummary]
    pagination: PaginationInfo


class USDANutrientMeasurement(BaseModel):
    """Nutrient laboratory measurement per 100g edible portion."""

    nutrient_id: int = Field(..., example=1003)
    name: str = Field(..., example="Protein")
    unit_name: str = Field(..., example="G")
    amount_per_100g: Optional[float] = Field(
        None, description="Nutrient amount per 100 grams of food", example=16.89
    )
    data_points: Optional[int] = Field(None, example=5)


class USDAFoodPortion(BaseModel):
    """Standard household portion metric for a USDA food item."""

    id: int = Field(..., example=87123)
    seq_num: Optional[int] = Field(None, example=1)
    amount: Optional[float] = Field(None, example=1.0)
    portion_description: Optional[str] = Field(None, example="1 cup")
    modifier: Optional[str] = Field(None, example="uncooked")
    gram_weight: float = Field(..., example=81.0)


class USDAFoodDetail(BaseModel):
    """Complete nutrient breakdown and household portion data for a USDA food item."""

    fdc_id: int = Field(..., example=170554)
    data_type: str = Field(..., example="sr_legacy_food")
    description: str = Field(..., example="Oats, whole grain, rolled")
    food_category_id: Optional[int] = Field(None, example=20)
    publication_date: Optional[date] = Field(None, example="2019-04-01")
    nutrients: List[USDANutrientMeasurement] = Field(default_factory=list)
    portions: List[USDAFoodPortion] = Field(default_factory=list)


class RecipeIngredientInput(BaseModel):
    """Ingredient item input for recipe nutrition estimation."""

    raw_text: str = Field(..., example="2 cups whole rolled oats")
    canonical_name: Optional[str] = Field(None, example="rolled oats")
    quantity: Optional[float] = Field(None, example=2.0)
    unit: Optional[str] = Field(None, example="cup")
    quantity_g: Optional[float] = Field(
        None, description="Gram weight equivalent if known", example=160.0
    )
    fdc_id: Optional[int] = Field(
        None, description="Optional pre-mapped USDA Food identifier", example=170554
    )


class RecipeNutritionEstimateRequest(BaseModel):
    """Payload for calculating nutrient profile from raw ingredients."""

    servings: int = Field(default=1, ge=1, example=4)
    ingredients: List[RecipeIngredientInput] = Field(..., min_length=1, max_length=100)


class NutrientValues(BaseModel):
    """Aggregated nutritional metrics."""

    calories_kcal: Optional[float] = Field(None, example=607.2)
    total_fat_g: Optional[float] = Field(None, example=10.8)
    saturated_fat_g: Optional[float] = Field(None, example=1.9)
    carbohydrates_g: Optional[float] = Field(None, example=103.2)
    sugar_g: Optional[float] = Field(None, example=1.2)
    protein_g: Optional[float] = Field(None, example=26.3)
    sodium_mg: Optional[float] = Field(None, example=6.4)
    fiber_g: Optional[float] = Field(None, example=16.5)


class IngredientCoverage(BaseModel):
    """Coverage ratio of mapped ingredients."""

    mapped_count: int = Field(..., example=2)
    total_count: int = Field(..., example=2)
    coverage_pct: float = Field(..., ge=0.0, le=100.0, example=100.0)


class RecipeNutritionEstimateResponse(BaseModel):
    """Evaluated nutrient profile for submitted ingredients."""

    status: Literal["calculated", "reported_approximate", "partial", "uncalculated"] = Field(
        ..., description="Confidence status based on coverage threshold (>= 80% is calculated)", example="calculated"
    )
    ingredient_coverage: IngredientCoverage
    servings: int = Field(..., example=4)
    totals: Optional[NutrientValues] = None
    per_serving: Optional[NutrientValues] = None
    unmapped_ingredients: List[str] = Field(default_factory=list, example=[])
    provenance_note: Optional[str] = Field(
        None, example="Aggregated from USDA FoodData Central SR Legacy items (170554, 746782)."
    )
    disclaimer: str = Field(
        default="Nutritional values are mathematical estimates based on ingredient approximations and may vary."
    )


class CachedRecipeNutrition(BaseModel):
    """Cached nutritional estimation record from profile_nutrition.nutrition_estimates."""

    recipe_id: str = Field(..., example="rcp_foodcom_5421")
    status: Literal["calculated", "reported_approximate", "uncalculated"] = Field(
        ..., example="reported_approximate"
    )
    calories_kcal: Optional[float] = Field(None, example=385.4)
    total_fat_g: Optional[float] = Field(None, example=14.2)
    saturated_fat_g: Optional[float] = Field(None, example=3.5)
    carbohydrates_g: Optional[float] = Field(None, example=52.8)
    sugar_g: Optional[float] = Field(None, example=None)
    protein_g: Optional[float] = Field(None, example=12.1)
    sodium_mg: Optional[float] = Field(None, example=480.0)
    fiber_g: Optional[float] = Field(None, example=None)
    ingredient_coverage_pct: Optional[float] = Field(None, example=None)
    mapped_ingredient_count: Optional[int] = Field(None, example=None)
    total_ingredient_count: Optional[int] = Field(None, example=8)
    servings: Optional[int] = Field(None, example=4)
    provenance_note: Optional[str] = Field(
        None, example="Reported in Food.com dataset (RAW_recipes.csv)."
    )
    calculated_at: datetime = Field(..., example="2026-11-03T07:00:00Z")
    updated_at: datetime = Field(..., example="2026-11-03T07:00:00Z")

