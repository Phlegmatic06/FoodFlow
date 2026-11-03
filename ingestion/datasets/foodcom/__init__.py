"""Food.com Recipes & Interactions Ingestion Package

Provides safe streaming parsing, schema validation, batch PostgreSQL loading,
ratings aggregation via temporary staging, and manifest auditing.
"""

from ingestion.datasets.foodcom.importer import FoodComImporter, FoodComReport
from ingestion.datasets.foodcom.loader import FoodComLoader
from ingestion.datasets.foodcom.parser import FoodComParseError, FoodComSource
from ingestion.datasets.foodcom.ratings import RatingsAggregationMetrics, RatingsAggregator
from ingestion.datasets.foodcom.validator import (
    FoodComValidationError,
    UnmatchedRecipeError,
    ValidatedInteraction,
    ValidatedRecipe,
)

__all__ = [
    "FoodComImporter",
    "FoodComReport",
    "FoodComSource",
    "FoodComLoader",
    "RatingsAggregator",
    "RatingsAggregationMetrics",
    "FoodComParseError",
    "FoodComValidationError",
    "UnmatchedRecipeError",
    "ValidatedRecipe",
    "ValidatedInteraction",
]
