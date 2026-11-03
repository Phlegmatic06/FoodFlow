"""RecipeNLG Dataset Ingestion Package

Provides streaming parser, record validation, PostgreSQL batch loading,
and pipeline orchestration for the RecipeNLG dataset (~2.23M recipes).
"""

from ingestion.datasets.recipenlg.importer import RecipeNLGImporter, RecipeNLGReport
from ingestion.datasets.recipenlg.loader import RecipeNLGLoader
from ingestion.datasets.recipenlg.parser import (
    RecipeNLGParseError,
    RecipeNLGSource,
    clean_text,
    parse_ingredient_amount_and_unit,
    safe_parse_list,
)
from ingestion.datasets.recipenlg.validator import (
    DuplicateRecipeIDError,
    RecipeNLGValidationError,
    ValidatedRecipeNLG,
    validate_headers,
    validate_recipe_record,
)


__all__ = [
    "RecipeNLGImporter",
    "RecipeNLGReport",
    "RecipeNLGLoader",
    "RecipeNLGSource",
    "RecipeNLGParseError",
    "RecipeNLGValidationError",
    "DuplicateRecipeIDError",
    "ValidatedRecipeNLG",
    "validate_headers",
    "validate_recipe_record",
    "safe_parse_list",
    "clean_text",
    "parse_ingredient_amount_and_unit",
]
