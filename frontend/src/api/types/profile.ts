/**
 * Profile & Nutrition Service Types
 * Derived from contracts/openapi/profile-service.yaml
 */

export type BiologicalSex = 'male' | 'female';
export type ActivityLevel =
  | 'sedentary'
  | 'lightly_active'
  | 'moderately_active'
  | 'very_active'
  | 'extra_active';
export type NutritionGoal = 'maintain' | 'lose' | 'gain';
export type BMICategory =
  | 'underweight'
  | 'normal_weight'
  | 'overweight'
  | 'obesity_class_1'
  | 'obesity_class_2'
  | 'obesity_class_3';

export interface MacroTargets {
  protein_g: number;
  carbohydrates_g: number;
  fat_g: number;
}

export interface MacroRangePercentage {
  min_pct: number;
  max_pct: number;
}

export interface MacroRangesPercent {
  protein: MacroRangePercentage;
  carbohydrates: MacroRangePercentage;
  fat: MacroRangePercentage;
}

export interface BiometricsCalculationRequest {
  age_years: number;
  sex_for_equation?: BiologicalSex | null;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  goal?: NutritionGoal;
}

export interface BiometricsCalculationResponse {
  bmi: number;
  bmi_category: BMICategory;
  bmr_kcal: number | null;
  tdee_kcal: number | null;
  target_calories_kcal: number | null;
  formula: string;
  activity_multiplier: number | null;
  goal: NutritionGoal;
  goal_adjustment_kcal: number | null;
  macro_targets_grams: MacroTargets | null;
  macro_ranges_percent: MacroRangesPercent;
  caveats: string[];
  disclaimer: string;
}

export interface UserTargetSummary {
  user_id?: string;
  target_calories_kcal: number;
  macro_targets_grams: MacroTargets;
  macro_ranges_percent: MacroRangesPercent;
  disclaimer: string;
}

export interface USDAFoodSummary {
  fdc_id: number;
  data_type: string;
  description: string;
  food_category_id?: number | null;
  publication_date?: string | null;
}

export interface PaginatedUSDAFoodSummary {
  data: USDAFoodSummary[];
  pagination: {
    page: number;
    limit: number;
    total_items: number;
    total_pages: number;
  };
}

export interface USDANutrientMeasurement {
  nutrient_id: number;
  name: string;
  unit_name: string;
  amount_per_100g: number | null;
  data_points?: number | null;
}

export interface USDAFoodPortion {
  id: number;
  gram_weight: number;
  portion_description?: string | null;
  modifier?: string | null;
  amount?: number | null;
  measure_unit_id?: number | null;
}

export interface USDAFoodDetail extends USDAFoodSummary {
  nutrients: USDANutrientMeasurement[];
  portions: USDAFoodPortion[];
}

export interface NutrientValues {
  calories_kcal?: number | null;
  total_fat_g?: number | null;
  saturated_fat_g?: number | null;
  carbohydrates_g?: number | null;
  sugar_g?: number | null;
  protein_g?: number | null;
  sodium_mg?: number | null;
  fiber_g?: number | null;
}

export interface IngredientCoverage {
  mapped_count: number;
  total_count: number;
  coverage_pct: number;
}

export type NutritionStatus = 'calculated' | 'reported_approximate' | 'partial' | 'uncalculated';

export interface CachedRecipeNutrition {
  recipe_id: string;
  status: NutritionStatus;
  calories_kcal?: number | null;
  total_fat_g?: number | null;
  saturated_fat_g?: number | null;
  carbohydrates_g?: number | null;
  sugar_g?: number | null;
  protein_g?: number | null;
  sodium_mg?: number | null;
  fiber_g?: number | null;
  ingredient_coverage_pct?: number | null;
  mapped_ingredient_count?: number | null;
  total_ingredient_count?: number | null;
  servings?: number | null;
  provenance_note?: string | null;
  calculated_at: string;
  updated_at: string;
}

export interface RecipeIngredientInput {
  raw_text: string;
  canonical_name?: string | null;
  quantity?: number | null;
  unit?: string | null;
  quantity_g?: number | null;
  fdc_id?: number | null;
}

export interface RecipeNutritionEstimateRequest {
  servings?: number;
  ingredients: RecipeIngredientInput[];
}

export interface RecipeNutritionEstimateResponse {
  status: NutritionStatus;
  ingredient_coverage: IngredientCoverage;
  servings: number;
  totals?: NutrientValues | null;
  per_serving?: NutrientValues | null;
  unmapped_ingredients: string[];
  provenance_note?: string | null;
  disclaimer: string;
}

