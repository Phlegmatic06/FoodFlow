"""FoodFlow Ingestion Framework Configuration

Centralizes filesystem paths, database configuration, dataset metadata,
batch parameters, and environment variable lookups.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse


# -----------------------------------------------------------------------------
# Base Directories
# -----------------------------------------------------------------------------
def get_project_root() -> Path:
    """Return the repository root directory."""
    env_root = os.getenv("FOODFLOW_ROOT_DIR")
    if env_root:
        return Path(env_root).resolve()
    # ingestion/config.py -> ingestion -> root
    return Path(__file__).resolve().parent.parent


ROOT_DIR: Path = get_project_root()
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DATA_DIR: Path = DATA_DIR / "raw"
USDA_RAW_DIR: Path = RAW_DATA_DIR / "usda"
FOODCOM_RAW_DIR: Path = RAW_DATA_DIR / "foodcom"
RECIPENLG_RAW_DIR: Path = RAW_DATA_DIR / "recipenlg"
PROCESSED_DATA_DIR: Path = DATA_DIR / "processed"
REPORTS_DIR: Path = DATA_DIR / "reports"
MANIFEST_PATH: Path = DATA_DIR / "manifest.json"

# Ingestion configuration defaults
DEFAULT_BATCH_SIZE: int = int(os.getenv("FOODFLOW_BATCH_SIZE", "1000"))
CSV_FIELD_SIZE_LIMIT: int = 2147483647  # 2^31 - 1, safe on both 32-bit and 64-bit platforms


# -----------------------------------------------------------------------------
# Dataset Source Definitions
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class DatasetMetadata:
    identifier: str
    display_name: str
    official_source_url: str
    target_schema: str
    expected_files: List[str]
    raw_directory: Path
    license_terms: str
    reference_citation: str
    source_version: Optional[str] = None
    notes: Optional[str] = None


DATASET_REGISTRY: Dict[str, DatasetMetadata] = {
    "usda": DatasetMetadata(
        identifier="usda_fdc",
        display_name="USDA FoodData Central (FDC)",
        official_source_url="https://fdc.nal.usda.gov/download-datasets/",
        target_schema="profile_nutrition",
        expected_files=[
            "food.csv",
            "nutrient.csv",
            "food_nutrient.csv",
            "food_portion.csv",
        ],
        raw_directory=USDA_RAW_DIR,
        license_terms="Public Domain (CC0 1.0 Universal) - U.S. Government Work",
        reference_citation="U.S. Department of Agriculture, Agricultural Research Service. FoodData Central.",
        source_version="SR Legacy & Foundation Foods",
        notes="Powers profile_nutrition nutritional reference dictionary per 100g.",
    ),
    "foodcom": DatasetMetadata(
        identifier="food_com",
        display_name="Food.com Recipes and Interactions",
        official_source_url="https://berd-platform.de/records/0455w-b0633",
        target_schema="recipe_catalog",
        expected_files=[
            "RAW_recipes.csv",
            "RAW_interactions.csv",
        ],
        raw_directory=FOODCOM_RAW_DIR,
        license_terms="Non-commercial academic research and educational evaluation",
        reference_citation="Majumder, B. P., Li, S., Ni, J., & McAuley, J. (2019). Generating Personalized Recipes from Historical User Preferences. EMNLP.",
        source_version="Kaggle/BERD 2019 Snapshot",
        notes="Provides rich metadata, 7-element %DV nutrition, tags, and user ratings.",
    ),
    "recipenlg": DatasetMetadata(
        identifier="recipenlg",
        display_name="RecipeNLG Large Scale Recipe Corpus",
        official_source_url="https://recipenlg.cs.put.poznan.pl/dataset",
        target_schema="recipe_catalog",
        expected_files=[
            "full_dataset.csv",
        ],
        raw_directory=RECIPENLG_RAW_DIR,
        license_terms="Non-commercial research and educational usage agreement",
        reference_citation="Bień, M., Gilski, M., Maciejewska, M., Taisner, W., Wisniewski, D., & Lawrynowicz, A. (2020). RecipeNLG: A Large Scale Dataset for Recipe Generation and Evaluation.",
        source_version="1.0.0",
        notes="High-volume corpus (~2.23M recipes) with pre-extracted NER ingredient tokens.",
    ),
}

# Alias mapping for CLI convenience
DATASET_ALIASES: Dict[str, str] = {
    "usda": "usda",
    "usda_fdc": "usda",
    "foodcom": "foodcom",
    "food_com": "foodcom",
    "food-com": "foodcom",
    "recipenlg": "recipenlg",
    "recipe_nlg": "recipenlg",
    "recipe-nlg": "recipenlg",
}


def resolve_dataset_key(key: str) -> Optional[str]:
    """Normalize input dataset name to registry key ('usda', 'foodcom', 'recipenlg')."""
    return DATASET_ALIASES.get(key.lower().strip())


# -----------------------------------------------------------------------------
# USDA Sub-Collection Definitions
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class USDACollectionMetadata:
    collection_id: str
    display_name: str
    official_source_url: str
    release_date: str
    data_type_tag: str
    expected_files: List[str]
    notes: str


USDA_COLLECTIONS: Dict[str, USDACollectionMetadata] = {
    "foundation": USDACollectionMetadata(
        collection_id="foundation",
        display_name="USDA Foundation Foods",
        official_source_url="https://fdc.nal.usda.gov/download-datasets/",
        release_date="October 2026",
        data_type_tag="foundation_food",
        expected_files=[
            "food.csv",
            "nutrient.csv",
            "food_nutrient.csv",
            "food_portion.csv",
        ],
        notes="Modern nutrient analyses containing detailed per-100g values for basic commodity ingredients.",
    ),
    "sr_legacy": USDACollectionMetadata(
        collection_id="sr_legacy",
        display_name="USDA SR Legacy",
        official_source_url="https://fdc.nal.usda.gov/download-datasets/",
        release_date="April 2018",
        data_type_tag="sr_legacy_food",
        expected_files=[
            "food.csv",
            "nutrient.csv",
            "food_nutrient.csv",
            "food_portion.csv",
        ],
        notes="Authoritative historical composition data for staple ingredients.",
    ),
}

USDA_COLLECTION_ALIASES: Dict[str, str] = {
    "foundation": "foundation",
    "foundation_foods": "foundation",
    "foundation-foods": "foundation",
    "sr_legacy": "sr_legacy",
    "sr-legacy": "sr_legacy",
    "srlegacy": "sr_legacy",
    "legacy": "sr_legacy",
}


def resolve_usda_collection_key(key: str) -> Optional[str]:
    """Normalize input USDA collection identifier to 'foundation' or 'sr_legacy'."""
    return USDA_COLLECTION_ALIASES.get(key.lower().strip())


# -----------------------------------------------------------------------------
# Database Configuration & Safety
# -----------------------------------------------------------------------------
def get_database_url() -> Optional[str]:
    """Retrieve database connection URL from environment variables."""
    return os.getenv("DATABASE_URL") or os.getenv("FOODFLOW_DATABASE_URL")


def mask_database_url(url: Optional[str]) -> str:
    """Mask password in a database connection URL for safe logging and status reporting."""
    if not url:
        return "<NOT_SET>"
    try:
        parsed = urlparse(url)
        if not parsed.password:
            return url
        # Reconstruct with masked password
        netloc = f"{parsed.username or ''}:********@{parsed.hostname or ''}"
        if parsed.port:
            netloc += f":{parsed.port}"
        masked = parsed._replace(netloc=netloc)
        return urlunparse(masked)
    except Exception:
        return "<INVALID_URL_FORMAT>"


def ensure_directories_exist() -> None:
    """Ensure all required data and report directories exist on disk."""
    for directory in [
        USDA_RAW_DIR,
        FOODCOM_RAW_DIR,
        RECIPENLG_RAW_DIR,
        PROCESSED_DATA_DIR,
        REPORTS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

