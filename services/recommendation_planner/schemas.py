"""Pydantic schemas conforming strictly to OpenAPI contract for Planner Service."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

SlotType = Literal["breakfast", "lunch", "dinner", "snack"]
CookingStatus = Literal["pending", "cooked", "skipped"]


class PaginationInfo(BaseModel):
    """Offset-limit pagination metadata."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="Current page number")
    limit: int = Field(default=24, ge=1, le=48, description="Maximum items per page")
    total_items: int = Field(..., ge=0, description="Total matching items across all pages")
    total_pages: int = Field(..., ge=0, description="Total pages available")


# =========================================================================
# GUEST SESSIONS
# =========================================================================


class GuestSessionResponse(BaseModel):
    """Anonymous guest session token and validity window."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., description="UUID guest session identifier")
    created_at: datetime = Field(..., description="ISO 8601 creation timestamp")
    expires_at: datetime = Field(..., description="ISO 8601 expiration timestamp")
    last_active_at: datetime = Field(..., description="ISO 8601 last active timestamp")


# =========================================================================
# PANTRY INVENTORY
# =========================================================================


class PantryItem(BaseModel):
    """Pantry item record stored in meal_planner.pantry_session_items."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Item ID")
    raw_name: str = Field(..., description="Raw ingredient text as entered by guest")
    canonical_ingredient_id: Optional[int] = Field(
        default=None,
        description="External reference to recipe_catalog.canonical_ingredients.id",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when ingredient was added",
    )


class PantryInventoryResponse(BaseModel):
    """Complete pantry inventory response."""

    model_config = ConfigDict(extra="forbid")

    items: List[PantryItem] = Field(default_factory=list, description="Pantry items")
    total_count: int = Field(..., ge=0, description="Total items in pantry")


class UpdatePantryItemInput(BaseModel):
    """Single item entry for replacing pantry inventory."""

    model_config = ConfigDict(extra="forbid")

    raw_name: str = Field(..., min_length=1, max_length=255, description="Raw ingredient text")
    canonical_ingredient_id: Optional[int] = Field(
        default=None,
        description="Optional external canonical ingredient reference",
    )


class UpdatePantryRequest(BaseModel):
    """Request payload to replace guest pantry inventory."""

    model_config = ConfigDict(extra="forbid")

    items: List[UpdatePantryItemInput] = Field(
        default_factory=list,
        description="Complete list of pantry items (empty list clears pantry)",
    )


# =========================================================================
# PANTRY-TO-RECIPE MATCHING
# =========================================================================


class PantryMatchRequest(BaseModel):
    """Parameters for finding recipes matching pantry ingredients."""

    model_config = ConfigDict(extra="forbid")

    ingredients: Optional[List[str]] = Field(
        default=None,
        description="Explicit ingredient strings (defaults to guest pantry if omitted)",
    )
    exclude_pantry_staples: bool = Field(
        default=True,
        description="Exclude basic staples (salt, water, pepper) from match denominator",
    )
    min_match_pct: float = Field(
        default=30.0,
        ge=0.0,
        le=100.0,
        description="Minimum match threshold percentage",
    )
    page: int = Field(default=1, ge=1, description="Page index")
    limit: int = Field(default=24, ge=1, le=48, description="Results per page")


class PantryMatchResultItem(BaseModel):
    """Individual recipe match result with ingredient overlap metrics."""

    model_config = ConfigDict(extra="forbid")

    recipe_id: str = Field(..., description="Unified global recipe identifier")
    title: str = Field(..., description="Recipe title")
    match_pct: float = Field(..., ge=0.0, le=100.0, description="Ingredient match percentage")
    matched_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients available in pantry",
    )
    missing_ingredients: List[str] = Field(
        default_factory=list,
        description="Ingredients required but missing from pantry",
    )
    total_recipe_ingredients: int = Field(
        ...,
        ge=0,
        description="Total distinct ingredient count for recipe",
    )
    total_time_minutes: Optional[int] = Field(
        default=None,
        description="Estimated total preparation and cooking time in minutes",
    )
    rating_average: Optional[float] = Field(
        default=None,
        description="Mean user rating (1.0 to 5.0) or null if unrated",
    )


class PantryMatchResponse(BaseModel):
    """Ranked recipe matches for pantry inventory."""

    model_config = ConfigDict(extra="forbid")

    matches: List[PantryMatchResultItem] = Field(
        default_factory=list,
        description="Ranked candidate recipes",
    )
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


# =========================================================================
# MEAL PLAN AUTO-GENERATION
# =========================================================================


class GenerateMealPlanRequest(BaseModel):
    """Parameters for automated meal plan generation proposal."""

    model_config = ConfigDict(extra="forbid")

    days: int = Field(default=1, ge=1, le=14, description="Number of days to schedule (1 to 14)")
    slots: List[SlotType] = Field(
        default=["breakfast", "lunch", "dinner"],
        min_length=1,
        description="Meal slot types per day",
    )
    target_calories_kcal: Optional[int] = Field(
        default=None,
        ge=800,
        le=6000,
        description="Optional daily caloric target",
    )
    cuisine_preference: Optional[str] = Field(
        default=None,
        description="Preferred cuisine name",
    )
    diet_preference: Optional[str] = Field(
        default=None,
        description="Dietary tag preference (e.g. vegetarian, vegan)",
    )
    max_time_per_recipe: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum cooking time in minutes",
    )
    pantry_ingredients: Optional[List[str]] = Field(
        default=None,
        description="Optional on-hand ingredients to prioritize",
    )


class GeneratedSlotProposal(BaseModel):
    """Individual meal slot proposed in generated plan."""

    model_config = ConfigDict(extra="forbid")

    slot_type: SlotType = Field(..., description="Meal slot designation")
    recipe_id: str = Field(..., description="Unified global recipe identifier")
    title: str = Field(..., description="Recipe title")
    total_time_minutes: Optional[int] = Field(
        default=None,
        description="Total preparation & cooking time in minutes",
    )
    estimated_calories_kcal: Optional[float] = Field(
        default=None,
        description="Estimated calories per serving if available",
    )


class GeneratedDayPlan(BaseModel):
    """Proposed schedule for a single day."""

    model_config = ConfigDict(extra="forbid")

    day_index: int = Field(..., ge=0, description="Zero-based day offset")
    slots: List[GeneratedSlotProposal] = Field(
        default_factory=list,
        description="Proposed slots for this day",
    )
    day_total_calories_kcal: Optional[float] = Field(
        default=None,
        description="Summed calories for the day",
    )


class GeneratedMealPlanResponse(BaseModel):
    """Auto-generated meal plan proposal."""

    model_config = ConfigDict(extra="forbid")

    target_calories_kcal: Optional[int] = Field(
        default=None,
        description="Target daily calories applied",
    )
    days: List[GeneratedDayPlan] = Field(..., description="Day-by-day proposed meals")
    notes: Optional[List[str]] = Field(
        default=None,
        description="Informational notes regarding substitutions or constraints",
    )


# =========================================================================
# MEAL PLAN PERSISTENCE
# =========================================================================


class MealPlanSlotInput(BaseModel):
    """Slot definition for saving or updating a meal plan."""

    model_config = ConfigDict(extra="forbid")

    day_index: int = Field(..., ge=0, description="Zero-based day offset")
    slot_type: SlotType = Field(..., description="Meal designation")
    recipe_id: str = Field(
        ...,
        pattern=r"^rcp_(foodcom|nlg)_[a-zA-Z0-9_-]+$",
        description="Unified global recipe identifier",
    )
    recipe_title: str = Field(..., min_length=1, max_length=512, description="Recipe title snapshot")


class SaveMealPlanRequest(BaseModel):
    """Payload to persist or replace a multi-day meal plan."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255, description="Name of the meal plan")
    target_calories_kcal: Optional[int] = Field(
        default=None,
        ge=1,
        description="Optional daily caloric target",
    )
    days: int = Field(default=1, ge=1, le=14, description="Number of days (1 to 14)")
    slots: List[MealPlanSlotInput] = Field(
        ...,
        min_length=1,
        description="Ordered list of meal slots",
    )


class SavedMealPlanSummary(BaseModel):
    """Compact confirmation of newly saved meal plan."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(..., description="UUID of created meal plan")
    name: str = Field(..., description="Plan name")
    days: int = Field(..., description="Number of days")
    created_at: datetime = Field(..., description="Creation timestamp")


class MealPlanSlotDetail(BaseModel):
    """Full detail of a persistent meal plan slot including cooking progress."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Slot ID")
    day_index: int = Field(..., ge=0, description="Zero-based day offset")
    slot_type: SlotType = Field(..., description="Meal designation")
    recipe_id: str = Field(..., description="Unified global recipe identifier")
    recipe_title: str = Field(..., description="Recipe title snapshot")
    cooking_status: CookingStatus = Field(
        default="pending",
        description="Execution state: pending, cooked, or skipped",
    )
    status_updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last cooking status transition",
    )


class MealPlanDetail(BaseModel):
    """Complete representation of a saved meal plan."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="UUID meal plan identifier")
    name: str = Field(..., description="Meal plan name")
    target_calories_kcal: Optional[int] = Field(
        default=None,
        description="Daily caloric target",
    )
    days: int = Field(..., description="Number of days spanned")
    slots: List[MealPlanSlotDetail] = Field(
        default_factory=list,
        description="All slots across all scheduled days",
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# =========================================================================
# SHOPPING LIST
# =========================================================================


class ShoppingListItem(BaseModel):
    """Item on a consolidated grocery list."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Item ID")
    ingredient_name: str = Field(..., description="Name of ingredient")
    quantity_display: Optional[str] = Field(
        default=None,
        description="Formatted quantity and unit if known",
    )
    category: Optional[str] = Field(
        default=None,
        description="Supermarket department / grouping category",
    )
    checked: bool = Field(default=False, description="Procurement check state")


class ShoppingListCategoryGroup(BaseModel):
    """Category grouping for supermarket navigation."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(..., description="Category name (e.g. Produce, Dairy, Pantry)")
    items: List[ShoppingListItem] = Field(
        default_factory=list,
        description="Items in this category",
    )


class ShoppingListResponse(BaseModel):
    """Consolidated grocery shopping list response."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="UUID shopping list identifier")
    plan_id: str = Field(..., description="UUID of associated meal plan")
    categories: List[ShoppingListCategoryGroup] = Field(
        default_factory=list,
        description="Grouped items by category",
    )
    total_items: int = Field(..., ge=0, description="Total line items on shopping list")


class UpdateShoppingItemRequest(BaseModel):
    """Toggle procurement state of a shopping list item."""

    model_config = ConfigDict(extra="forbid")

    checked: bool = Field(..., description="New checked status")


# =========================================================================
# COOKING PROGRESS
# =========================================================================


class SlotCookingProgressUpdate(BaseModel):
    """Update instruction for a single meal plan slot."""

    model_config = ConfigDict(extra="forbid")

    slot_id: int = Field(..., description="Slot ID to update")
    cooking_status: CookingStatus = Field(..., description="New execution state")


class UpdateCookingProgressRequest(BaseModel):
    """Batch progress recording for meal plan slots."""

    model_config = ConfigDict(extra="forbid")

    updates: List[SlotCookingProgressUpdate] = Field(
        ...,
        min_length=1,
        description="Slot progress updates",
    )


class UpdateProgressResponse(BaseModel):
    """Confirmation of cooking status updates."""

    model_config = ConfigDict(extra="forbid")

    updated_count: int = Field(..., ge=0, description="Number of slots updated")
    plan_id: str = Field(..., description="UUID meal plan identifier")

