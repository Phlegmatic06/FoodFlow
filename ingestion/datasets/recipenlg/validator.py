"""RecipeNLG Record and Schema Validation

Validates CSV column structures, enforces relational invariants,
sanitizes stringified lists (ingredients, directions, NER),
maps source origin sub-corpora (Gathered, Recipes1M),
and handles malformed records with explicit accounting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.datasets.recipenlg.parser import (
    RecipeNLGParseError,
    clean_text,
    safe_parse_list,
)


REQUIRED_RECIPENLG_HEADERS = {"id", "title", "ingredients", "directions", "link", "source"}
OPTIONAL_RECIPENLG_HEADERS = {"ner"}


class RecipeNLGValidationError(Exception):
    """Raised when a RecipeNLG CSV record fails validation."""

    def __init__(self, line_number: int, reason: str, field_name: Optional[str] = None):
        super().__init__(f"Line {line_number}: {reason}")
        self.line_number = line_number
        self.reason = reason
        self.field_name = field_name


class DuplicateRecipeIDError(RecipeNLGValidationError):
    """Raised when a duplicate recipe ID is detected in the input stream."""

    def __init__(self, line_number: int, source_id: str):
        super().__init__(line_number, f"Duplicate RecipeNLG source id: {source_id!r}", "id")
        self.source_id = source_id


@dataclass(frozen=True)
class ValidatedRecipeNLG:
    """Validated, normalized RecipeNLG record ready for database staging or dry-run auditing."""

    id: str  # Format: rcp_nlg_{source_id}
    source_id: str  # Original dataset ID (including '0')
    source_dataset: str  # Fixed: 'recipenlg'
    title: str  # Truncated to 512 chars
    source_origin: Optional[str]  # 'Gathered', 'Recipes1M', or None
    source_url: Optional[str]  # Original link
    ingredients: List[str]  # Non-empty list of raw ingredient strings
    instructions: List[str]  # Ordered directions (may be empty if unavailable in source)
    ner_entities: Optional[List[str]]  # Extracted food entities, or None if malformed/missing
    line_number: int
    has_ner_failure: bool = False
    has_missing_directions: bool = False


def validate_headers(actual_headers: List[str]) -> Tuple[bool, List[str]]:
    """Verify that all required RecipeNLG headers exist, supporting case variations."""
    actual_set = {h.strip().lower() for h in actual_headers}
    missing = sorted(list(REQUIRED_RECIPENLG_HEADERS - actual_set))
    return len(missing) == 0, missing


def _lookup_field(row: Dict[str, str], *candidate_names: str) -> Optional[str]:
    """Look up a field value from row dictionary case-insensitively across aliases."""
    for cand in candidate_names:
        cand_lower = cand.lower()
        for k, v in row.items():
            if k.strip().lower() == cand_lower:
                return v
    return None


def validate_recipe_record(
    row: Dict[str, str],
    line_number: int,
    seen_ids: Optional[Set[str]] = None,
) -> ValidatedRecipeNLG:
    """Validate and coerce a single row from RecipeNLG full_dataset.csv.
    
    Rules:
      1. id: Must be a non-negative integer (e.g. 0, 108294).
      2. title: Must not be empty. Truncated to 512 characters.
      3. ingredients: Must be a valid list containing non-empty strings.
      4. directions: Must be a valid list of strings. Empty list is accepted (flagged).
      5. ner: If malformed, recorded as failure but recipe is preserved.
      6. source: Normalized to 'Gathered', 'Recipes1M', or raw value.
    """
    # 1. Recipe ID
    raw_id = clean_text(_lookup_field(row, "id"))
    if raw_id is None:
        raise RecipeNLGValidationError(line_number, "Missing mandatory recipe id", "id")

    try:
        int_id = int(float(raw_id))
        if int_id < 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise RecipeNLGValidationError(line_number, f"Invalid recipe id: {raw_id!r}", "id")

    source_id = str(int_id)
    if seen_ids is not None:
        if source_id in seen_ids:
            raise DuplicateRecipeIDError(line_number, source_id)
        seen_ids.add(source_id)

    unified_id = f"rcp_nlg_{source_id}"

    # 2. Title
    raw_title = clean_text(_lookup_field(row, "title", "name"))
    if not raw_title:
        raise RecipeNLGValidationError(line_number, "Missing mandatory recipe title", "title")
    title = raw_title[:512]

    # 3. Source Origin (Gathered vs Recipes1M)
    raw_source = clean_text(_lookup_field(row, "source"))
    source_origin: Optional[str] = None
    if raw_source:
        lower_source = raw_source.lower()
        if lower_source in ("gathered", "1"):
            source_origin = "Gathered"
        elif lower_source in ("recipes1m", "recipe1m", "0"):
            source_origin = "Recipes1M"
        else:
            source_origin = None

    # 4. Source URL / Link
    source_url = clean_text(_lookup_field(row, "link", "url"))

    # 5. Ingredients list (Mandatory non-empty)
    raw_ingredients = _lookup_field(row, "ingredients")
    try:
        ingredients = safe_parse_list(raw_ingredients, "ingredients", line_number)
        if not ingredients:
            raise RecipeNLGValidationError(line_number, "Recipe has empty ingredients list", "ingredients")
    except RecipeNLGParseError as pe:
        raise RecipeNLGValidationError(line_number, str(pe), "ingredients") from pe

    # 6. Directions / Instructions (Optional in source, but list syntax must be valid)
    raw_directions = _lookup_field(row, "directions", "steps", "instructions")
    has_missing_directions = False
    try:
        instructions = safe_parse_list(raw_directions, "directions", line_number)
        if not instructions:
            has_missing_directions = True
    except RecipeNLGParseError as pe:
        raise RecipeNLGValidationError(line_number, str(pe), "directions") from pe

    # 7. NER Entities (Named Entity Recognition)
    raw_ner = _lookup_field(row, "ner")
    ner_entities: Optional[List[str]] = None
    has_ner_failure = False
    if raw_ner:
        try:
            ner_entities = safe_parse_list(raw_ner, "ner", line_number)
        except RecipeNLGParseError:
            # Tolerant degradation: NER failure does not invalidate the recipe
            has_ner_failure = True
            ner_entities = None

    return ValidatedRecipeNLG(
        id=unified_id,
        source_id=source_id,
        source_dataset="recipenlg",
        title=title,
        source_origin=source_origin,
        source_url=source_url,
        ingredients=ingredients,
        instructions=instructions,
        ner_entities=ner_entities,
        line_number=line_number,
        has_ner_failure=has_ner_failure,
        has_missing_directions=has_missing_directions,
    )

