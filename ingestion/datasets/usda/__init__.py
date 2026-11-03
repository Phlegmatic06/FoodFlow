"""USDA FoodData Central Ingestion Package

Provides streaming parsing, schema validation, batch PostgreSQL loading,
and manifest auditing for Foundation Foods and SR Legacy collections.
"""

from ingestion.datasets.usda.importer import IngestionReport, USDAImporter
from ingestion.datasets.usda.loader import USDALoader
from ingestion.datasets.usda.parser import USDAParseError, USDASource
from ingestion.datasets.usda.validator import (
    USDAValidationError,
    ValidatedFood,
    ValidatedFoodNutrient,
    ValidatedFoodPortion,
    ValidatedNutrient,
)

__all__ = [
    "USDAImporter",
    "IngestionReport",
    "USDASource",
    "USDALoader",
    "USDAParseError",
    "USDAValidationError",
    "ValidatedFood",
    "ValidatedNutrient",
    "ValidatedFoodNutrient",
    "ValidatedFoodPortion",
]
