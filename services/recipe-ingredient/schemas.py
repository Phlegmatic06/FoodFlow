"""Pydantic schemas for the Recipe & Ingredient Service matching OpenAPI contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PaginationInfo(BaseModel):
    """Metadata describing paginated result collection."""

    page: int = Field(..., ge=1, example=1)
    limit: int = Field(..., ge=1, le=48, example=24)
    total_items: int = Field(..., ge=0, example=84)
    total_pages: int = Field(..., ge=0, example=4)


class RecipeSummary(BaseModel):
    """Condensed recipe representation for catalogue listings and search cards."""

    id: str = Field(..., example="rcp_foodcom_5421")
    source_dataset: Literal["food_com", "recipenlg"] = Field(..., example="food_com")
    source_id: str = Field(..., example="5421")
    title: str = Field(..., example="Classic Rosemary Garlic Roasted Chicken")
    description: Optional[str] = Field(
        None,
        example="Succulent whole roasted chicken infused with fresh rosemary and roasted garlic cloves.",
    )
    prep_time_minutes: Optional[int] = Field(None, example=15)
    cook_time_minutes: Optional[int] = Field(None, example=60)
    total_time_minutes: Optional[int] = Field(None, example=75)
    servings: Optional[int] = Field(
        None,
        description="Number of servings yield. Strictly null for RecipeNLG records.",
        example=4,
    )
    cuisine: Optional[str] = Field(None, example="Mediterranean")
    source_url: Optional[str] = Field(
        None, example="https://www.food.com/recipe/rosemary-chicken-5421"
    )
    rating_average: Optional[float] = Field(
        None, description="Average review rating from 1.00 to 5.00. NULL if unrated.", example=4.75
    )
    rating_count: int = Field(
        default=0, description="Number of user reviews. 0 if unrated.", example=28
    )
    tag_preview: List[str] = Field(
        default_factory=list,
        max_length=5,
        example=["dinner", "chicken", "poultry", "roast", "gluten-free"],
    )


class PaginatedRecipeSummary(BaseModel):
    """Paginated collection of recipe summaries."""

    data: List[RecipeSummary]
    pagination: PaginationInfo


class RecipeIngredientItem(BaseModel):
    """Individual recipe ingredient item retaining verbatim string and parsed metrics."""

    position: int = Field(..., example=1)
    raw_text: str = Field(
        ..., description="Original verbatim ingredient string from dataset", example="3 lbs whole chicken"
    )
    canonical_ingredient_id: Optional[int] = Field(None, example=101)
    canonical_name: Optional[str] = Field(None, example="whole chicken")
    quantity: Optional[float] = Field(None, example=3.0)
    unit: Optional[str] = Field(None, example="lb")


class RecipeInstructionItem(BaseModel):
    """Sequential preparation step for hands-on guided cooking."""

    step_number: int = Field(..., example=1)
    instruction: str = Field(
        ..., example="Preheat oven to 375 degrees F (190 degrees C). Lightly oil a roasting pan."
    )


class RecipeRawNutrition(BaseModel):
    """Raw reported nutrition metrics from Food.com RAW_recipes.csv."""

    raw_calories: float = Field(..., description="Energy in kilocalories (kcal)", example=385.4)
    raw_total_fat_pdv: Optional[float] = Field(
        None, description="Total Fat percentage Daily Value (%DV)", example=22.0
    )
    raw_sugar_pdv: Optional[float] = Field(
        None, description="Sugar percentage Daily Value (%DV)", example=2.0
    )
    raw_sodium_pdv: Optional[float] = Field(
        None, description="Sodium percentage Daily Value (%DV)", example=18.0
    )
    raw_protein_pdv: Optional[float] = Field(
        None, description="Protein percentage Daily Value (%DV)", example=54.0
    )
    raw_saturated_fat_pdv: Optional[float] = Field(
        None, description="Saturated Fat percentage Daily Value (%DV)", example=17.0
    )
    raw_carbohydrates_pdv: Optional[float] = Field(
        None, description="Carbohydrates percentage Daily Value (%DV)", example=1.0
    )


class RecipeDetail(BaseModel):
    """Complete detailed recipe representation including ordered ingredients and steps."""

    id: str = Field(..., example="rcp_foodcom_5421")
    source_dataset: Literal["food_com", "recipenlg"] = Field(..., example="food_com")
    source_id: str = Field(..., example="5421")
    title: str = Field(..., example="Classic Rosemary Garlic Roasted Chicken")
    description: Optional[str] = Field(
        None,
        example="Succulent whole roasted chicken infused with fresh rosemary and roasted garlic cloves.",
    )
    prep_time_minutes: Optional[int] = Field(None, example=15)
    cook_time_minutes: Optional[int] = Field(None, example=60)
    total_time_minutes: Optional[int] = Field(None, example=75)
    servings: Optional[int] = Field(None, example=4)
    cuisine: Optional[str] = Field(None, example="Mediterranean")
    source_url: Optional[str] = Field(
        None, example="https://www.food.com/recipe/rosemary-chicken-5421"
    )
    submitted_date: Optional[date] = Field(None, example="2002-04-18")
    created_at: datetime = Field(..., example="2026-11-03T07:00:00Z")
    rating_average: Optional[float] = Field(None, example=4.75)
    rating_count: int = Field(default=0, example=28)
    ingredients: List[RecipeIngredientItem] = Field(default_factory=list)
    instructions: List[RecipeInstructionItem] = Field(default_factory=list)
    tags: List[str] = Field(
        default_factory=list, example=["dinner", "chicken", "poultry", "roast", "gluten-free"]
    )
    raw_nutrition: Optional[RecipeRawNutrition] = None


class BatchRecipeRequest(BaseModel):
    """Payload requesting batch retrieval of recipes by ID list."""

    recipe_ids: List[str] = Field(..., min_length=1, max_length=100)
    fields: Optional[List[str]] = Field(None)


class BatchRecipeResponse(BaseModel):
    """Results of batch recipe lookup."""

    recipes: List[RecipeDetail]
    not_found: List[str] = Field(default_factory=list)


class NormalizeIngredientsRequest(BaseModel):
    """Payload for normalizing free-form ingredient text."""

    ingredients: List[str] = Field(..., min_length=1, max_length=50)


class NormalizedIngredientResult(BaseModel):
    """Canonical match result for a single ingredient input."""

    raw_input: str = Field(..., example="boneless chicken thighs")
    matched: bool = Field(..., example=True)
    canonical_id: Optional[int] = Field(None, example=102)
    canonical_name: Optional[str] = Field(None, example="chicken thigh")
    category: Optional[str] = Field(None, example="poultry")
    is_pantry_staple: Optional[bool] = Field(None, example=False)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, example=0.95)


class NormalizeIngredientsResponse(BaseModel):
    """Collection of normalized ingredient mappings."""

    results: List[NormalizedIngredientResult]


class IngredientSuggestion(BaseModel):
    """Autocomplete suggestion candidate for canonical ingredients."""

    id: int = Field(..., example=102)
    name: str = Field(..., example="chicken thigh")
    category: Optional[str] = Field(None, example="poultry")
    is_pantry_staple: bool = Field(default=False, example=False)


class SearchByIngredientsRequest(BaseModel):
    """Request payload for retrieving candidate recipes by canonical ingredient IDs."""

    canonical_ingredient_ids: List[int] = Field(..., min_length=1, max_length=50)
    exclude_pantry_staples: bool = Field(default=True)
    min_match_pct: float = Field(default=20.0, ge=0.0, le=100.0)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=24, ge=1, le=48)


class IngredientCandidateItem(BaseModel):
    """Candidate recipe containing one or more queried canonical ingredients."""

    recipe_id: str = Field(..., example="rcp_foodcom_5421")
    title: str = Field(..., example="Classic Rosemary Garlic Roasted Chicken")
    source_dataset: str = Field(..., example="food_com")
    total_time_minutes: Optional[int] = Field(None, example=75)
    servings: Optional[int] = Field(None, example=4)
    rating_average: Optional[float] = Field(None, example=4.75)
    rating_count: int = Field(default=0, example=28)
    matched_canonical_ids: List[int] = Field(default_factory=list)
    recipe_canonical_ids: List[int] = Field(default_factory=list)
    total_recipe_ingredients: int = Field(..., example=4)
    match_pct: float = Field(..., example=50.0)


class PaginatedIngredientCandidates(BaseModel):
    """Paginated collection of candidate recipes matched by canonical ingredients."""

    data: List[IngredientCandidateItem]
    pagination: PaginationInfo
