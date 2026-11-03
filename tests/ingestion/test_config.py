"""Unit tests for ingestion configuration and metadata registry."""

import os
import unittest
from pathlib import Path

from ingestion.config import (
    DATASET_REGISTRY,
    ROOT_DIR,
    USDA_RAW_DIR,
    FOODCOM_RAW_DIR,
    RECIPENLG_RAW_DIR,
    ensure_directories_exist,
    get_database_url,
    get_project_root,
    mask_database_url,
    resolve_dataset_key,
)


class TestIngestionConfig(unittest.TestCase):

    def test_project_root_discovery(self):
        root = get_project_root()
        self.assertIsInstance(root, Path)
        self.assertTrue((root / "ingestion").exists())
        self.assertTrue((root / "database").exists())

    def test_dataset_registry_completeness(self):
        self.assertIn("usda", DATASET_REGISTRY)
        self.assertIn("foodcom", DATASET_REGISTRY)
        self.assertIn("recipenlg", DATASET_REGISTRY)

        # USDA metadata
        usda = DATASET_REGISTRY["usda"]
        self.assertEqual(usda.target_schema, "profile_nutrition")
        self.assertEqual(usda.identifier, "usda_fdc")
        self.assertEqual(len(usda.expected_files), 4)
        self.assertIn("food.csv", usda.expected_files)

        # Food.com metadata
        foodcom = DATASET_REGISTRY["foodcom"]
        self.assertEqual(foodcom.target_schema, "recipe_catalog")
        self.assertEqual(foodcom.identifier, "food_com")
        self.assertIn("RAW_recipes.csv", foodcom.expected_files)
        self.assertIn("RAW_interactions.csv", foodcom.expected_files)

        # RecipeNLG metadata
        recipenlg = DATASET_REGISTRY["recipenlg"]
        self.assertEqual(recipenlg.target_schema, "recipe_catalog")
        self.assertEqual(recipenlg.identifier, "recipenlg")
        self.assertIn("full_dataset.csv", recipenlg.expected_files)

    def test_alias_resolution(self):
        self.assertEqual(resolve_dataset_key("usda"), "usda")
        self.assertEqual(resolve_dataset_key("USDA_FDC"), "usda")
        self.assertEqual(resolve_dataset_key("food_com"), "foodcom")
        self.assertEqual(resolve_dataset_key("foodcom"), "foodcom")
        self.assertEqual(resolve_dataset_key("recipe_nlg"), "recipenlg")
        self.assertEqual(resolve_dataset_key("recipenlg"), "recipenlg")
        self.assertIsNone(resolve_dataset_key("invalid_dataset_xyz"))

    def test_database_url_masking(self):
        self.assertEqual(mask_database_url(None), "<NOT_SET>")
        self.assertEqual(mask_database_url(""), "<NOT_SET>")

        plain_url = "postgresql://localhost:5432/foodflow_db"
        self.assertEqual(mask_database_url(plain_url), plain_url)

        auth_url = "postgresql://foodflow_admin:secret123@db.internal:5432/foodflow_db"
        masked = mask_database_url(auth_url)
        self.assertNotIn("secret123", masked)
        self.assertIn("foodflow_admin", masked)
        self.assertIn("db.internal:5432", masked)
        self.assertIn("********", masked)

    def test_directory_creation(self):
        ensure_directories_exist()
        self.assertTrue(USDA_RAW_DIR.exists())
        self.assertTrue(FOODCOM_RAW_DIR.exists())
        self.assertTrue(RECIPENLG_RAW_DIR.exists())


if __name__ == "__main__":
    unittest.main()

