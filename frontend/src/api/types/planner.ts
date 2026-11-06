/**
 * Recommendation & Meal Planner Service Types
 * Derived from contracts/openapi/planner-service.yaml
 */

export interface GuestSession {
  session_id: string;
  created_at: string;
  expires_at: string;
  last_active_at: string;
}

export interface PantryItem {
  id: number;
  raw_name: string;
  canonical_ingredient_id?: number | null;
  created_at?: string;
}

export interface PantryInventoryResponse {
  items: PantryItem[];
  total_count: number;
}

export interface UpdatePantryItemInput {
  raw_name: string;
  canonical_ingredient_id?: number | null;
}

export interface UpdatePantryRequest {
  items: UpdatePantryItemInput[];
}

export interface PantryMatchRequest {
  ingredients?: string[];
  exclude_pantry_staples?: boolean;
  min_match_pct?: number;
  page?: number;
  limit?: number;
}

export interface PantryMatchResultItem {
  recipe_id: string;
  title: string;
  match_pct: number;
  matched_ingredients: string[];
  missing_ingredients: string[];
  total_recipe_ingredients: number;
  total_time_minutes?: number | null;
  rating_average?: number | null;
}

export interface PantryMatchResponse {
  matches: PantryMatchResultItem[];
  data?: PantryMatchResultItem[];
  pagination: {
    page: number;
    limit: number;
    total_items: number;
    total_pages: number;
  };
}

// ----------------------------------------------------------------------------
// Meal Planning: Types & Schemas
// ----------------------------------------------------------------------------

export type MealSlotType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

export type CookingStatus = 'pending' | 'cooked' | 'skipped';

export interface GenerateMealPlanRequest {
  days: number;
  slots: MealSlotType[];
  target_calories_kcal?: number | null;
  cuisine_preference?: string | null;
  diet_preference?: string | null;
  max_time_per_recipe?: number | null;
  pantry_ingredients?: string[];
}

export interface GeneratedSlotProposal {
  slot_type: MealSlotType;
  recipe_id: string;
  title: string;
  total_time_minutes?: number | null;
  estimated_calories_kcal?: number | null;
}

export interface GeneratedDayPlan {
  day_index: number;
  slots: GeneratedSlotProposal[];
  day_total_calories_kcal?: number | null;
}

export interface GeneratedMealPlanResponse {
  target_calories_kcal?: number | null;
  days: GeneratedDayPlan[];
  notes?: string[];
}

export interface MealPlanSlotInput {
  day_index: number;
  slot_type: MealSlotType;
  recipe_id: string;
  recipe_title: string;
}

export interface SaveMealPlanRequest {
  name: string;
  target_calories_kcal?: number | null;
  days: number;
  slots: MealPlanSlotInput[];
  // Backwards-compatibility aliases
  title?: string;
  target_calories_daily?: number;
}

export interface SavedMealPlanSummary {
  plan_id: string;
  name: string;
  days: number;
  created_at: string;
}

export interface MealPlanSlotDetail {
  id: number;
  day_index: number;
  slot_type: MealSlotType;
  recipe_id: string;
  recipe_title: string;
  cooking_status: CookingStatus;
  status_updated_at?: string | null;
  // Backwards-compatibility aliases
  day_number?: number;
  meal_type?: string;
}

export interface MealPlanDetail {
  id: string;
  name: string;
  target_calories_kcal?: number | null;
  days: number;
  slots: MealPlanSlotDetail[];
  created_at: string;
  updated_at: string;
  // Backwards-compatibility aliases
  title?: string;
  target_calories_daily?: number;
}

export interface SlotCookingProgressUpdate {
  slot_id: number;
  cooking_status: CookingStatus;
}

export interface UpdateCookingProgressRequest {
  updates: SlotCookingProgressUpdate[];
}

export interface UpdateProgressResponse {
  updated_count: number;
  plan_id: string;
}

// ----------------------------------------------------------------------------
// Shopping List: Types & Schemas
// ----------------------------------------------------------------------------

export interface ShoppingListItem {
  id: number;
  ingredient_name: string;
  quantity_display?: string | null;
  category?: string | null;
  checked: boolean;
  // Backwards-compatibility aliases
  canonical_ingredient_id?: number | null;
  total_quantity?: number | null;
  unit?: string | null;
  is_in_pantry?: boolean;
  recipe_ids?: string[];
}

export interface ShoppingListCategoryGroup {
  category: string;
  items: ShoppingListItem[];
}

export interface ShoppingListResponse {
  id?: string;
  plan_id: string;
  categories: ShoppingListCategoryGroup[];
  total_items: number;
  // Backwards-compatibility aliases
  items?: ShoppingListItem[];
  already_in_pantry_count?: number;
  needed_count?: number;
}

export interface UpdateShoppingItemRequest {
  checked: boolean;
}

// ----------------------------------------------------------------------------
// Legacy / Deprecated Aliases for Previous Steps
// ----------------------------------------------------------------------------

export interface ProposeMealPlanRequest {
  days: number;
  target_calories_daily: number;
  calorie_tolerance_pct?: number;
  meals_per_day?: number;
  dietary_preferences?: string[];
  excluded_ingredient_canonical_ids?: number[];
  diversity_penalty?: number;
}

export interface MealPlanProposalSlot {
  day_number: number;
  meal_type: MealSlotType;
  recipe_id: string;
  recipe_title: string;
  estimated_calories: number;
}

export interface MealPlanProposalResponse {
  proposal_id: string;
  days: number;
  target_calories_daily: number;
  total_plan_calories: number;
  average_daily_calories: number;
  slots: MealPlanProposalSlot[];
}
