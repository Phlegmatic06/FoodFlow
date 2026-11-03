"""USDA FoodData Central Record & Header Validation

Validates CSV schemas, enforces relational constraints, checks mandatory fields,
and provides detailed line-numbered error accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.datasets.usda.parser import clean_text, parse_date, parse_float, parse_int


# -----------------------------------------------------------------------------
# Required CSV Headers per Target Table
# -----------------------------------------------------------------------------
REQUIRED_HEADERS = {
    "food.csv": {"fdc_id", "description"},
    "nutrient.csv": {"id", "name", "unit_name"},
    "food_nutrient.csv": {"id", "fdc_id", "nutrient_id"},
    "food_portion.csv": {"id", "fdc_id", "gram_weight"},
}


class USDAValidationError(Exception):
    """Raised when a single record fails business logic or relational checks."""

    def __init__(self, line_number: int, reason: str, field_name: Optional[str] = None):
        super().__init__(f"Line {line_number}: {reason}")
        self.line_number = line_number
        self.reason = reason
        self.field_name = field_name


# -----------------------------------------------------------------------------
# Validated Data Classes
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class ValidatedFood:
    fdc_id: int
    data_type: str
    description: str
    food_category_id: Optional[int]
    publication_date: Optional[str]


@dataclass(frozen=True)
class ValidatedNutrient:
    id: int
    name: str
    unit_name: str
    nutrient_nbr: Optional[str]
    rank: Optional[float]


@dataclass(frozen=True)
class ValidatedFoodNutrient:
    id: int
    fdc_id: int
    nutrient_id: int
    amount: Optional[float]
    data_points: Optional[int]
    derivation_id: Optional[int]


@dataclass(frozen=True)
class ValidatedFoodPortion:
    id: int
    fdc_id: int
    seq_num: Optional[int]
    amount: Optional[float]
    measure_unit_id: Optional[int]
    portion_description: Optional[str]
    modifier: Optional[str]
    gram_weight: float


# -----------------------------------------------------------------------------
# Validation Functions
# -----------------------------------------------------------------------------
def validate_headers(file_name: str, actual_headers: List[str]) -> Tuple[bool, List[str]]:
    """Verify that all required headers for a USDA file exist in actual headers."""
    canonical = file_name.lower()
    required = REQUIRED_HEADERS.get(canonical, set())
    actual_set = {h.strip().lower() for h in actual_headers}
    missing = sorted(list(required - actual_set))
    return len(missing) == 0, missing


def validate_food_record(
    row: Dict[str, str],
    line_number: int,
    default_data_type: str,
) -> ValidatedFood:
    """Validate and coerce a single food.csv row."""
    # 1. fdc_id
    raw_fdc_id = row.get("fdc_id")
    if not raw_fdc_id:
        raise USDAValidationError(line_number, "Missing required fdc_id", "fdc_id")
    try:
        fdc_id = parse_int(raw_fdc_id, "fdc_id")
        if fdc_id is None or fdc_id <= 0:
            raise ValueError()
    except ValueError:
        raise USDAValidationError(line_number, f"Invalid fdc_id: {raw_fdc_id!r}", "fdc_id")

    # 2. description
    description = clean_text(row.get("description"))
    if not description:
        raise USDAValidationError(line_number, "Missing required food description", "description")

    # 3. data_type
    data_type = clean_text(row.get("data_type")) or default_data_type

    # 4. food_category_id
    try:
        food_category_id = parse_int(row.get("food_category_id"), "food_category_id")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "food_category_id")

    # 5. publication_date
    try:
        publication_date = parse_date(row.get("publication_date"), "publication_date")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "publication_date")

    return ValidatedFood(
        fdc_id=fdc_id,
        data_type=data_type,
        description=description,
        food_category_id=food_category_id,
        publication_date=publication_date,
    )


def validate_nutrient_record(
    row: Dict[str, str],
    line_number: int,
) -> ValidatedNutrient:
    """Validate and coerce a single nutrient.csv row."""
    # 1. id
    raw_id = row.get("id")
    if not raw_id:
        raise USDAValidationError(line_number, "Missing required nutrient id", "id")
    try:
        nutrient_id = parse_int(raw_id, "id")
        if nutrient_id is None or nutrient_id <= 0:
            raise ValueError()
    except ValueError:
        raise USDAValidationError(line_number, f"Invalid nutrient id: {raw_id!r}", "id")

    # 2. name
    name = clean_text(row.get("name"))
    if not name:
        raise USDAValidationError(line_number, "Missing required nutrient name", "name")

    # 3. unit_name
    unit_name = clean_text(row.get("unit_name"))
    if not unit_name:
        raise USDAValidationError(line_number, "Missing required nutrient unit_name", "unit_name")

    # 4. nutrient_nbr
    nutrient_nbr = clean_text(row.get("nutrient_nbr"))

    # 5. rank
    try:
        rank = parse_float(row.get("rank"), "rank")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "rank")

    return ValidatedNutrient(
        id=nutrient_id,
        name=name,
        unit_name=unit_name,
        nutrient_nbr=nutrient_nbr,
        rank=rank,
    )


def validate_food_nutrient_record(
    row: Dict[str, str],
    line_number: int,
    known_foods: Optional[Set[int]] = None,
    known_nutrients: Optional[Set[int]] = None,
) -> ValidatedFoodNutrient:
    """Validate and coerce a single food_nutrient.csv row, verifying referential integrity."""
    # 1. id
    raw_id = row.get("id")
    if not raw_id:
        raise USDAValidationError(line_number, "Missing required food_nutrient id", "id")
    try:
        record_id = parse_int(raw_id, "id")
        if record_id is None or record_id <= 0:
            raise ValueError()
    except ValueError:
        raise USDAValidationError(line_number, f"Invalid food_nutrient id: {raw_id!r}", "id")

    # 2. fdc_id
    raw_fdc_id = row.get("fdc_id")
    try:
        fdc_id = parse_int(raw_fdc_id, "fdc_id")
        if fdc_id is None or fdc_id <= 0:
            raise ValueError()
    except ValueError:
        raise USDAValidationError(line_number, f"Invalid fdc_id in nutrient measurement: {raw_fdc_id!r}", "fdc_id")

    if known_foods is not None and fdc_id not in known_foods:
        raise USDAValidationError(line_number, f"Foreign key violation: fdc_id {fdc_id} not found in foods table", "fdc_id")

    # 3. nutrient_id
    raw_nutrient_id = row.get("nutrient_id")
    try:
        nutrient_id = parse_int(raw_nutrient_id, "nutrient_id")
        if nutrient_id is None or nutrient_id <= 0:
            raise ValueError()
    except ValueError:
        raise USDAValidationError(line_number, f"Invalid nutrient_id in measurement: {raw_nutrient_id!r}", "nutrient_id")

    if known_nutrients is not None and nutrient_id not in known_nutrients:
        raise USDAValidationError(line_number, f"Foreign key violation: nutrient_id {nutrient_id} not found in nutrients table", "nutrient_id")

    # 4. amount (allowed to be NULL if unmeasured; must NOT be replaced with 0)
    try:
        amount = parse_float(row.get("amount"), "amount")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "amount")

    # 5. data_points
    try:
        data_points = parse_int(row.get("data_points"), "data_points")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "data_points")

    # 6. derivation_id
    try:
        derivation_id = parse_int(row.get("derivation_id"), "derivation_id")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "derivation_id")

    return ValidatedFoodNutrient(
        id=record_id,
        fdc_id=fdc_id,
        nutrient_id=nutrient_id,
        amount=amount,
        data_points=data_points,
        derivation_id=derivation_id,
    )


def validate_food_portion_record(
    row: Dict[str, str],
    line_number: int,
    known_foods: Optional[Set[int]] = None,
) -> ValidatedFoodPortion:
    """Validate and coerce a single food_portion.csv row."""
    # 1. id
    raw_id = row.get("id")
    if not raw_id:
        raise USDAValidationError(line_number, "Missing required food_portion id", "id")
    try:
        portion_id = parse_int(raw_id, "id")
        if portion_id is None or portion_id <= 0:
            raise ValueError()
    except ValueError:
        raise USDAValidationError(line_number, f"Invalid portion id: {raw_id!r}", "id")

    # 2. fdc_id
    raw_fdc_id = row.get("fdc_id")
    try:
        fdc_id = parse_int(raw_fdc_id, "fdc_id")
        if fdc_id is None or fdc_id <= 0:
            raise ValueError()
    except ValueError:
        raise USDAValidationError(line_number, f"Invalid fdc_id in portion record: {raw_fdc_id!r}", "fdc_id")

    if known_foods is not None and fdc_id not in known_foods:
        raise USDAValidationError(line_number, f"Foreign key violation: fdc_id {fdc_id} not found in foods table", "fdc_id")

    # 3. gram_weight (NOT NULL in schema)
    raw_gram = row.get("gram_weight")
    if not raw_gram:
        raise USDAValidationError(line_number, "Missing mandatory gram_weight in portion record", "gram_weight")
    try:
        gram_weight = parse_float(raw_gram, "gram_weight")
        if gram_weight is None or gram_weight <= 0:
            raise ValueError("gram_weight must be strictly positive")
    except ValueError as e:
        raise USDAValidationError(line_number, f"Invalid gram_weight: {e}", "gram_weight")

    # Optional fields
    try:
        seq_num = parse_int(row.get("seq_num"), "seq_num")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "seq_num")

    try:
        amount = parse_float(row.get("amount"), "amount")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "amount")

    try:
        measure_unit_id = parse_int(row.get("measure_unit_id"), "measure_unit_id")
    except ValueError as e:
        raise USDAValidationError(line_number, str(e), "measure_unit_id")

    portion_description = clean_text(row.get("portion_description"))
    modifier = clean_text(row.get("modifier"))

    return ValidatedFoodPortion(
        id=portion_id,
        fdc_id=fdc_id,
        seq_num=seq_num,
        amount=amount,
        measure_unit_id=measure_unit_id,
        portion_description=portion_description,
        modifier=modifier,
        gram_weight=gram_weight,
    )

