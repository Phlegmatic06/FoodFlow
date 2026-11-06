/**
 * Recipe & Ingredient Service Types
 * Derived from contracts/openapi/recipe-service.yaml
 */

export type RecipeSortOption = 'relevance' | 'rating' | 'time_asc' | 'time_desc';
export type RecipeSourceDataset = 'food_com' | 'recipenlg';

export interface RecipeSummary {
  id: string;
  source_dataset: RecipeSourceDataset;
  source_id: string;
  title: string;
  description?: string | null;
  prep_time_minutes?: number | null;
  cook_time_minutes?: number | null;
  total_time_minutes?: number | null;
  servings?: number | null;
  cuisine?: string | null;
  source_url?: string | null;
  rating_average?: number | null;
  rating_count: number;
  tag_preview: string[];
}

export interface PaginationInfo {
  page: number;
  limit: number;
  total_items: number;
  total_pages: number;
}

export interface PaginatedRecipeSummary {
  data: RecipeSummary[];
  pagination: PaginationInfo;
}

export interface RecipeIngredientItem {
  position: number;
  raw_text: string;
  canonical_ingredient_id?: number | null;
  canonical_name?: string | null;
  quantity?: number | null;
  unit?: string | null;
}

export interface RecipeInstructionItem {
  step_number: number;
  instruction: string;
}

export interface RecipeRawNutrition {
  raw_calories: number;
  raw_total_fat_pdv?: number | null;
  raw_sugar_pdv?: number | null;
  raw_sodium_pdv?: number | null;
  raw_protein_pdv?: number | null;
  raw_saturated_fat_pdv?: number | null;
  raw_carbohydrates_pdv?: number | null;
}

export interface RecipeDetail {
  id: string;
  source_dataset: RecipeSourceDataset;
  source_id: string;
  title: string;
  description?: string | null;
  prep_time_minutes?: number | null;
  cook_time_minutes?: number | null;
  total_time_minutes?: number | null;
  servings?: number | null;
  cuisine?: string | null;
  source_url?: string | null;
  submitted_date?: string | null;
  created_at: string;
  rating_average?: number | null;
  rating_count: number;
  ingredients: RecipeIngredientItem[];
  instructions: RecipeInstructionItem[];
  tags: string[];
  raw_nutrition?: RecipeRawNutrition | null;
}

export interface RecipeSearchParams {
  q?: string;
  cuisine?: string;
  tag?: string;
  diet?: string;
  max_time?: number;
  source_dataset?: RecipeSourceDataset;
  sort?: RecipeSortOption;
  page?: number;
  limit?: number;
}

export interface NormalizedIngredientResult {
  raw_input: string;
  matched: boolean;
  canonical_id?: number | null;
  canonical_name?: string | null;
  category?: string | null;
  is_pantry_staple?: boolean;
  match_confidence?: number;
}

export interface NormalizeIngredientsResponse {
  results: NormalizedIngredientResult[];
}

export interface IngredientSuggestion {
  id: number;
  name: string;
  category?: string | null;
  is_pantry_staple?: boolean;
}

export interface CanonicalIngredientDetail {
  id: number;
  name: string;
  category: string;
  is_pantry_staple: boolean;
  synonyms: string[];
  recipe_usage_count?: number;
}
