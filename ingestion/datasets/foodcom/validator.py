"""Food.com Record and Schema Validation

Validates CSV column structures, enforces relational invariants,
sanitizes stringified Python arrays, and accounts for malformed rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.datasets.foodcom.parser import (
    FoodComParseError,
    clean_text,
    parse_date,
    parse_nutrition_array,
    parse_time_minutes,
    safe_parse_python_list,
)


REQUIRED_RECIPE_HEADERS = {"name", "id", "ingredients", "steps", "nutrition"}
REQUIRED_INTERACTION_HEADERS = {"recipe_id", "rating"}


class FoodComValidationError(Exception):
    """Raised when a Food.com CSV record fails validation."""

    def __init__(self, line_number: int, reason: str, field_name: Optional[str] = None):
        super().__init__(f"Line {line_number}: {reason}")
        self.line_number = line_number
        self.reason = reason
        self.field_name = field_name


class UnmatchedRecipeError(Exception):
    """Raised when an interaction references a recipe_id not in the imported catalogue."""

    def __init__(self, recipe_id: str, line_number: int):
        super().__init__(f"Line {line_number}: recipe_id {recipe_id!r} not in catalog")
        self.recipe_id = recipe_id
        self.line_number = line_number


@dataclass(frozen=True)
class ValidatedRecipe:
    id: str  # Format: rcp_foodcom_{source_id}
    source_id: str
    source_dataset: str
    title: str
    description: Optional[str]
    total_time_minutes: Optional[int]
    prep_time_minutes: Optional[int]
    cook_time_minutes: Optional[int]
    servings: Optional[int]
    cuisine: Optional[str]
    source_url: Optional[str]
    submitted_date: Optional[str]
    ingredients: List[str]  # Ordered list of raw ingredient strings
    instructions: List[str]  # Ordered list of instruction steps
    tags: List[str]  # Normalized lowercase deduplicated tags
    nutrition: Tuple[float, float, float, float, float, float, float]  # 7-element raw %DV tuple

    @property
    def calories(self) -> float:
        """First element of nutrition tuple is calories (kcal)."""
        return self.nutrition[0]


@dataclass(frozen=True)
class ValidatedInteraction:
    recipe_id: str  # Format: rcp_foodcom_{source_id}
    source_id: str
    rating: float  # Scale: 1.0 to 5.0
    date: Optional[str] = None


def validate_headers(file_name: str, actual_headers: List[str]) -> Tuple[bool, List[str]]:
    """Verify that all required headers exist for Food.com files."""
    canonical = file_name.lower()
    actual_set = {h.strip().lower() for h in actual_headers}
    required: Set[str] = set()

    if "recipes" in canonical:
        required = REQUIRED_RECIPE_HEADERS
    elif "interactions" in canonical:
        required = REQUIRED_INTERACTION_HEADERS

    missing = sorted(list(required - actual_set))
    return len(missing) == 0, missing


def validate_recipe_record(
    row: Dict[str, str],
    line_number: int,
) -> ValidatedRecipe:
    """Validate and coerce a single row from RAW_recipes.csv."""
    # 1. Recipe ID
    raw_id = clean_text(row.get("id"))
    if not raw_id:
        raise FoodComValidationError(line_number, "Missing mandatory recipe id", "id")
    try:
        int_id = int(float(raw_id))
        if int_id <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise FoodComValidationError(line_number, f"Invalid recipe id: {raw_id!r}", "id")

    source_id = str(int_id)
    unified_id = f"rcp_foodcom_{source_id}"

    # 2. Title / Name
    raw_name = clean_text(row.get("name"))
    if not raw_name:
        raise FoodComValidationError(line_number, "Missing mandatory recipe name/title", "name")
    # Truncate title to 512 characters to strictly satisfy schema constraint
    title = raw_name[:512]

    # 3. Description
    description = clean_text(row.get("description"))

    # 4. Minutes -> total_time_minutes
    total_time = parse_time_minutes(row.get("minutes"), line_number)

    # 5. Submitted Date
    submitted_date = parse_date(row.get("submitted"))

    # 6. Source URL
    source_url = f"https://www.food.com/recipe/{source_id}"

    # 7. Ingredients list
    try:
        ingredients_list = safe_parse_python_list(row.get("ingredients"), "ingredients", line_number)
        cleaned_ingredients: List[str] = []
        for ing in ingredients_list:
            c = clean_text(ing)
            if c:
                cleaned_ingredients.append(c)
        if not cleaned_ingredients:
            raise FoodComValidationError(line_number, "Recipe has empty ingredients list", "ingredients")
    except (ValueError, FoodComParseError) as e:
        raise FoodComValidationError(line_number, str(e), "ingredients")

    # 8. Instructions / Steps
    try:
        steps_list = safe_parse_python_list(row.get("steps"), "steps", line_number)
        cleaned_steps: List[str] = []
        for step in steps_list:
            s = clean_text(step)
            if s:
                cleaned_steps.append(s)
        if not cleaned_steps:
            raise FoodComValidationError(line_number, "Recipe has empty instruction steps list", "steps")
    except (ValueError, FoodComParseError) as e:
        raise FoodComValidationError(line_number, str(e), "steps")

    # 9. Tags
    try:
        tags_list = safe_parse_python_list(row.get("tags"), "tags", line_number)
        seen_tags: Set[str] = set()
        cleaned_tags: List[str] = []
        for tag in tags_list:
            t = clean_text(tag)
            if t:
                # Lowercase, truncate to 128 chars to fit VARCHAR(128)
                norm_tag = t.lower()[:128]
                if norm_tag not in seen_tags:
                    seen_tags.add(norm_tag)
                    cleaned_tags.append(norm_tag)
    except (ValueError, FoodComParseError) as e:
        raise FoodComValidationError(line_number, str(e), "tags")

    # 10. Nutrition 7-element array
    try:
        nutrition = parse_nutrition_array(row.get("nutrition"), line_number)
    except (ValueError, FoodComParseError) as e:
        raise FoodComValidationError(line_number, str(e), "nutrition")

    return ValidatedRecipe(
        id=unified_id,
        source_id=source_id,
        source_dataset="food_com",
        title=title,
        description=description,
        total_time_minutes=total_time,
        prep_time_minutes=None,  # Food.com does not publish separate prep time
        cook_time_minutes=None,  # Food.com does not publish separate cook time
        servings=None,           # Food.com RAW_recipes does not provide serving yields
        cuisine=None,            # Unsupervised cuisine inference is prohibited
        source_url=source_url,
        submitted_date=submitted_date,
        ingredients=cleaned_ingredients,
        instructions=cleaned_steps,
        tags=cleaned_tags,
        nutrition=nutrition,
    )


def validate_interaction_record(
    row: Dict[str, str],
    line_number: int,
    known_recipe_ids: Optional[Set[str]] = None,
) -> ValidatedInteraction:
    """Validate and coerce a single row from RAW_interactions.csv."""
    # 1. Recipe ID
    raw_id = clean_text(row.get("recipe_id"))
    if not raw_id:
        raise FoodComValidationError(line_number, "Missing interaction recipe_id", "recipe_id")
    try:
        int_id = int(float(raw_id))
        if int_id <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise FoodComValidationError(line_number, f"Invalid interaction recipe_id: {raw_id!r}", "recipe_id")

    source_id = str(int_id)
    unified_id = f"rcp_foodcom_{source_id}"

    # Check against known recipes in catalog if provided
    if known_recipe_ids is not None and unified_id not in known_recipe_ids:
        raise UnmatchedRecipeError(unified_id, line_number)

    # 2. Rating (Scale: 1.0 to 5.0)
    raw_rating = clean_text(row.get("rating"))
    if not raw_rating:
        raise FoodComValidationError(line_number, "Missing rating value", "rating")
    try:
        rating_val = float(raw_rating)
    except (ValueError, TypeError):
        raise FoodComValidationError(line_number, f"Non-numeric rating: {raw_rating!r}", "rating")

    # Food.com interactions contain 0 when a user wrote a comment without a rating
    # Only valid ratings on the documented 1-5 scale contribute to average
    if rating_val < 1.0 or rating_val > 5.0:
        raise FoodComValidationError(
            line_number,
            f"Rating {rating_val} is outside documented 1-5 scale (unrated review)",
            "rating",
        )

    # 3. Optional Date
    date_val = parse_date(row.get("date"))

    return ValidatedInteraction(
        recipe_id=unified_id,
        source_id=source_id,
        rating=rating_val,
        date=date_val,
    )
