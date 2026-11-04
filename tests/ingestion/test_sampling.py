"""Comprehensive Unit Tests for FoodFlow Unified Dataset Sampling Engine (Step 03.5)

Tests:
  - Base sampling primitives (proportional quotas, reservoir sampling, determinism).
  - Food.com tag taxonomy, time bucketing, primary stratum assignment.
  - Food.com two-pass reservoir sampling and referential interaction filtering.
  - RecipeNLG provenance classification, NER richness, and directions status.
  - RecipeNLG two-pass reservoir sampling.
  - CSV header preservation, quoted newlines/commas, malformed row handling.
  - ZIP archive streaming without extraction.
  - Dry-run mode without disk writes.
  - Report accuracy and JSON serialization.
  - Integration compatibility with existing Food.com and RecipeNLG importers.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ingestion.datasets.foodcom.importer import FoodComImporter
from ingestion.datasets.recipenlg.importer import RecipeNLGImporter
from ingestion.sampling.base import (
    ReservoirSampler,
    StratifiedReservoirSampler,
    allocate_proportional_quotas,
    derive_stratum_seed,
)
from ingestion.sampling.foodcom_sampler import (
    CATEGORY_TAG_MAP,
    FoodComSampler,
    classify_cooking_time_bucket,
    classify_foodcom_category,
    determine_foodcom_stratum,
)
from ingestion.sampling.recipenlg_sampler import (
    RecipeNLGSampler,
    classify_directions_status,
    classify_ner_richness,
    classify_source_origin,
    determine_recipenlg_stratum,
)
from ingestion.sampling.reports import SamplingReport
from ingestion.utils.checksums import compute_file_sha256


class TestSamplingBaseAndProportions(unittest.TestCase):
    """Tests for core mathematical quota allocation and reservoir sampling primitives."""

    def test_proportional_quota_normal_case(self):
        stratum_counts = {
            "stratum_a": 500,
            "stratum_b": 300,
            "stratum_c": 200,
        }
        quotas = allocate_proportional_quotas(stratum_counts, target_total=100)
        self.assertEqual(sum(quotas.values()), 100)
        self.assertEqual(quotas["stratum_a"], 50)
        self.assertEqual(quotas["stratum_b"], 30)
        self.assertEqual(quotas["stratum_c"], 20)

    def test_proportional_quota_small_strata_protection(self):
        stratum_counts = {
            "large_main": 9950,
            "tiny_exotic": 5,
        }
        quotas = allocate_proportional_quotas(stratum_counts, target_total=100)
        self.assertEqual(sum(quotas.values()), 100)
        # Small stratum is guaranteed at least 1 allocation (if pop >= 1)
        self.assertGreaterEqual(quotas["tiny_exotic"], 1)
        self.assertLessEqual(quotas["tiny_exotic"], 5)
        self.assertEqual(quotas["large_main"] + quotas["tiny_exotic"], 100)

    def test_proportional_quota_target_greater_than_population(self):
        stratum_counts = {
            "s1": 10,
            "s2": 15,
        }
        quotas = allocate_proportional_quotas(stratum_counts, target_total=100)
        # Returns 100% census when population <= target
        self.assertEqual(quotas["s1"], 10)
        self.assertEqual(quotas["s2"], 15)
        self.assertEqual(sum(quotas.values()), 25)

    def test_proportional_quota_zero_or_negative_target(self):
        stratum_counts = {"s1": 50, "s2": 50}
        self.assertEqual(allocate_proportional_quotas(stratum_counts, 0), {"s1": 0, "s2": 0})
        self.assertEqual(allocate_proportional_quotas(stratum_counts, -10), {"s1": 0, "s2": 0})

    def test_proportional_quota_empty_or_zero_strata(self):
        self.assertEqual(allocate_proportional_quotas({}, 100), {})
        self.assertEqual(allocate_proportional_quotas({"s1": 0, "s2": 0}, 10), {"s1": 0, "s2": 0})

    def test_derive_stratum_seed_properties(self):
        seed1 = derive_stratum_seed(42, "breakfast__time_lte_15")
        seed2 = derive_stratum_seed(42, "breakfast__time_lte_15")
        seed_diff_stratum = derive_stratum_seed(42, "dinner__time_gt_60")
        seed_diff_base = derive_stratum_seed(100, "breakfast__time_lte_15")

        self.assertGreaterEqual(seed1, 0)
        self.assertLessEqual(seed1, 0x7FFFFFFF)
        self.assertEqual(seed1, seed2)
        self.assertNotEqual(seed1, seed_diff_stratum)
        self.assertNotEqual(seed1, seed_diff_base)

    def test_proportional_quota_dictionary_order_independence(self):
        # Permuting dictionary insertion order must yield 100% identical quotas
        base_data = [
            ("stratum_z", 100),
            ("stratum_a", 250),
            ("stratum_m", 50),
            ("stratum_c", 300),
            ("stratum_b", 120),
        ]
        dict1 = dict(base_data)
        dict2 = dict(reversed(base_data))
        dict3 = dict(sorted(base_data, key=lambda x: x[1]))

        q1 = allocate_proportional_quotas(dict1, target_total=200)
        q2 = allocate_proportional_quotas(dict2, target_total=200)
        q3 = allocate_proportional_quotas(dict3, target_total=200)

        self.assertEqual(q1, q2)
        self.assertEqual(q2, q3)

    def test_proportional_quota_target_less_than_active_strata(self):
        # When target sample size is strictly less than number of active strata (e.g. 3 targets for 5 strata)
        stratum_counts = {
            "s_tiny": 10,
            "s_large1": 1000,
            "s_large2": 800,
            "s_medium": 300,
            "s_large3": 500,
        }
        quotas = allocate_proportional_quotas(stratum_counts, target_total=3)
        self.assertEqual(sum(quotas.values()), 3)
        # 3 largest strata by population (s_large1, s_large2, s_large3) receive 1 each
        self.assertEqual(quotas["s_large1"], 1)
        self.assertEqual(quotas["s_large2"], 1)
        self.assertEqual(quotas["s_large3"], 1)
        self.assertEqual(quotas["s_medium"], 0)
        self.assertEqual(quotas["s_tiny"], 0)

    def test_proportional_quota_mathematical_invariants(self):
        # Invariants across arbitrary configurations
        configs = [
            ({"a": 100, "b": 100, "c": 100}, 50),
            ({"a": 1, "b": 1, "c": 1, "d": 1}, 2),
            ({"a": 10, "b": 20, "c": 30}, 60),
            ({"a": 10, "b": 20, "c": 30}, 100),
            ({"a": 1000, "b": 1, "c": 1, "d": 1}, 10),
        ]
        for counts, target in configs:
            total_pop = sum(counts.values())
            quotas = allocate_proportional_quotas(counts, target)
            # Invariant 1: Sum equals min(target, total_pop)
            self.assertEqual(sum(quotas.values()), min(target, total_pop))
            # Invariant 2: No stratum exceeds population
            for s, q in quotas.items():
                self.assertLessEqual(q, counts[s])
                self.assertGreaterEqual(q, 0)
            # Invariant 3: If target >= len(active), each active stratum gets >= 1
            if target >= len([s for s, c in counts.items() if c > 0]):
                for s, q in quotas.items():
                    if counts[s] > 0:
                        self.assertGreaterEqual(q, 1)

    def test_single_reservoir_sampler_determinism(self):
        items = list(range(100))
        sampler1 = ReservoirSampler(capacity=10, seed=42)
        sampler2 = ReservoirSampler(capacity=10, seed=42)
        sampler3 = ReservoirSampler(capacity=10, seed=999)

        for item in items:
            sampler1.feed(item)
            sampler2.feed(item)
            sampler3.feed(item)

        sample1 = sampler1.get_sample()
        sample2 = sampler2.get_sample()
        sample3 = sampler3.get_sample()

        self.assertEqual(sample1, sample2)
        self.assertEqual(len(sample1), 10)
        self.assertNotEqual(sample1, sample3)

    def test_single_reservoir_sampler_capacity_bound(self):
        sampler = ReservoirSampler(capacity=5, seed=42)
        for i in range(1000):
            sampler.feed(i)
        self.assertEqual(len(sampler.get_sample()), 5)
        self.assertEqual(sampler.total_seen, 1000)

    def test_stratified_reservoir_sampler(self):
        quotas = {"alpha": 3, "beta": 2}
        strat_sampler = StratifiedReservoirSampler(quotas, base_seed=42)

        for i in range(20):
            strat_sampler.feed("alpha", f"a_{i}")
        for i in range(15):
            strat_sampler.feed("beta", f"b_{i}")

        samples = strat_sampler.get_samples_by_stratum()
        self.assertEqual(len(samples["alpha"]), 3)
        self.assertEqual(len(samples["beta"]), 2)
        self.assertEqual(strat_sampler.total_selected, 5)
        self.assertEqual(strat_sampler.total_seen, 35)


class TestFoodComCategorization(unittest.TestCase):
    """Tests for Food.com tag mapping, cooking-time buckets, and stratum identification."""

    def test_classify_foodcom_category_explicit_tags(self):
        self.assertEqual(classify_foodcom_category(["breakfast", "pancakes"]), "breakfast")
        self.assertEqual(classify_foodcom_category(["lunch", "sandwiches"]), "lunch")
        self.assertEqual(classify_foodcom_category(["dinner", "pasta", "italian"]), "dinner")
        self.assertEqual(classify_foodcom_category(["desserts", "cakes", "sweet"]), "dessert")
        self.assertEqual(classify_foodcom_category(["appetizers", "snacks"]), "snack")
        self.assertEqual(classify_foodcom_category(["beverages", "cocktails"]), "beverage")

    def test_classify_foodcom_category_fallback_to_other(self):
        self.assertEqual(classify_foodcom_category([]), "other")
        self.assertEqual(classify_foodcom_category(["unrelated-tag", "special-occasion"]), "other")

    def test_classify_foodcom_category_precedence(self):
        # When tags match multiple categories, precedence order determines primary stratum:
        # Precedence: Breakfast -> Lunch -> Dinner -> Dessert -> Snack -> Beverage -> Other
        self.assertEqual(classify_foodcom_category(["dinner", "breakfast"]), "breakfast")
        self.assertEqual(classify_foodcom_category(["desserts", "lunch"]), "lunch")
        self.assertEqual(classify_foodcom_category(["beverages", "desserts"]), "dessert")

    def test_classify_cooking_time_buckets(self):
        self.assertEqual(classify_cooking_time_bucket(5), "time_lte_15")
        self.assertEqual(classify_cooking_time_bucket(15), "time_lte_15")
        self.assertEqual(classify_cooking_time_bucket(20), "time_16_30")
        self.assertEqual(classify_cooking_time_bucket(30), "time_16_30")
        self.assertEqual(classify_cooking_time_bucket(45), "time_31_60")
        self.assertEqual(classify_cooking_time_bucket(60), "time_31_60")
        self.assertEqual(classify_cooking_time_bucket(90), "time_gt_60")
        self.assertEqual(classify_cooking_time_bucket(0), "time_unknown")
        self.assertEqual(classify_cooking_time_bucket(-10), "time_unknown")
        self.assertEqual(classify_cooking_time_bucket(None), "time_unknown")

    def test_determine_foodcom_stratum_composite(self):
        row = {
            "tags": "['breakfast', 'easy']",
            "minutes": "10",
        }
        self.assertEqual(determine_foodcom_stratum(row), "breakfast__time_lte_15")

        row2 = {
            "tags": "['dinner', 'main-dish']",
            "minutes": "45",
        }
        self.assertEqual(determine_foodcom_stratum(row2), "dinner__time_31_60")


class TestFoodComSamplerPipeline(unittest.TestCase):
    """Tests for the end-to-end Food.com sampling and interaction filtering workflow."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.test_dir) / "source"
        self.output_dir = Path(self.test_dir) / "output"
        self.source_dir.mkdir(parents=True)

        # Create synthetic RAW_recipes.csv with rich metadata & quoted multiline fields
        self.recipes_csv = self.source_dir / "RAW_recipes.csv"
        self.interactions_csv = self.source_dir / "RAW_interactions.csv"

        # Headers
        self.recipe_headers = [
            "name", "id", "minutes", "contributor_id", "submitted",
            "tags", "nutrition", "n_steps", "steps", "description",
            "ingredients", "n_ingredients"
        ]

        # 8 synthetic recipes across strata (2 breakfast, 2 dinner, 2 dessert, 1 malformed, 1 other)
        self.synthetic_recipes = [
            {
                "name": "Classic Fluffy Pancakes",
                "id": "101",
                "minutes": "15",
                "contributor_id": "1",
                "submitted": "2020-01-01",
                "tags": "['breakfast', 'pancakes']",
                "nutrition": "[300.0, 10.0, 5.0, 15.0, 8.0, 4.0, 25.0]",
                "n_steps": "2",
                "steps": "['Mix batter, with comma.', 'Cook on griddle until golden.']",
                "description": "Delicious morning pancakes, fluffy and soft.",
                "ingredients": "['flour', 'milk', 'eggs']",
                "n_ingredients": "3",
            },
            {
                "name": "Quick Breakfast Waffles",
                "id": "102",
                "minutes": "10",
                "contributor_id": "1",
                "submitted": "2020-01-02",
                "tags": "['breakfast', 'waffles']",
                "nutrition": "[320.0, 12.0, 6.0, 16.0, 7.0, 5.0, 26.0]",
                "n_steps": "2",
                "steps": "['Pour in waffle iron.', 'Bake 5 mins.']",
                "description": "Crispy golden waffles.",
                "ingredients": "['flour', 'butter', 'syrup']",
                "n_ingredients": "3",
            },
            {
                "name": "Hearty Beef Stew",
                "id": "201",
                "minutes": "90",
                "contributor_id": "2",
                "submitted": "2020-02-01",
                "tags": "['dinner', 'stews', 'beef']",
                "nutrition": "[500.0, 20.0, 4.0, 30.0, 35.0, 8.0, 15.0]",
                "n_steps": "2",
                "steps": "['Brown the beef.', 'Simmer for 1 hour.']",
                "description": "Rich comfort food for cold winter evenings.",
                "ingredients": "['beef chuck', 'carrots', 'potatoes', 'beef broth']",
                "n_ingredients": "4",
            },
            {
                "name": "Weeknight Pasta Primavera",
                "id": "202",
                "minutes": "25",
                "contributor_id": "2",
                "submitted": "2020-02-05",
                "tags": "['dinner', 'pasta', 'main-dish']",
                "nutrition": "[420.0, 14.0, 5.0, 18.0, 12.0, 4.0, 35.0]",
                "n_steps": "2",
                "steps": "['Boil pasta.', 'Toss with vegetables.']",
                "description": "Fresh vegetables with pasta in light garlic sauce.",
                "ingredients": "['penne', 'bell peppers', 'olive oil', 'parmesan']",
                "n_ingredients": "4",
            },
            {
                "name": "Rich Chocolate Fudge Cake",
                "id": "301",
                "minutes": "50",
                "contributor_id": "3",
                "submitted": "2020-03-01",
                "tags": "['desserts', 'cakes', 'baking']",
                "nutrition": "[480.0, 22.0, 45.0, 12.0, 5.0, 10.0, 40.0]",
                "n_steps": "2",
                "steps": "['Mix cocoa and sugar.', 'Bake at 350F.']",
                "description": "Triple chocolate decadence.",
                "ingredients": "['cocoa powder', 'sugar', 'flour', 'eggs']",
                "n_ingredients": "4",
            },
            {
                "name": "Warm Berry Cobbler",
                "id": "302",
                "minutes": "40",
                "contributor_id": "3",
                "submitted": "2020-03-05",
                "tags": "['desserts', 'baking', 'cobblers']",
                "nutrition": "[350.0, 10.0, 35.0, 8.0, 3.0, 4.0, 32.0]",
                "n_steps": "2",
                "steps": "['Combine berries.', 'Top with biscuit dough and bake.']",
                "description": "Fresh summer berries baked under golden biscuits.",
                "ingredients": "['blackberries', 'blueberries', 'sugar', 'flour']",
                "n_ingredients": "4",
            },
            {
                "name": "Roasted Garlic Dip",
                "id": "401",
                "minutes": "30",
                "contributor_id": "4",
                "submitted": "2020-04-01",
                "tags": "['snacks', 'appetizers', 'dips-spreads']",
                "nutrition": "[150.0, 12.0, 1.0, 10.0, 3.0, 4.0, 5.0]",
                "n_steps": "2",
                "steps": "['Roast garlic cloves.', 'Blend with cream cheese.']",
                "description": "Savory roasted garlic party dip.",
                "ingredients": "['garlic', 'cream cheese', 'sour cream']",
                "n_ingredients": "3",
            },
            {
                # Malformed row to test rejection handling (id is invalid string)
                "name": "Malformed Recipe Record",
                "id": "invalid_id_999",
                "minutes": "10",
                "contributor_id": "5",
                "submitted": "2020-05-01",
                "tags": "['breakfast']",
                "nutrition": "[100.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]",
                "n_steps": "1",
                "steps": "['Invalid step']",
                "description": "This row must be safely rejected.",
                "ingredients": "['salt']",
                "n_ingredients": "1",
            },
        ]

        with open(self.recipes_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.recipe_headers)
            writer.writeheader()
            for r in self.synthetic_recipes:
                writer.writerow(r)

        # Interactions CSV (some match synthetic recipes, some point to other recipes)
        self.interaction_headers = ["user_id", "recipe_id", "date", "rating", "review"]
        self.synthetic_interactions = [
            {"user_id": "1001", "recipe_id": "101", "date": "2020-01-10", "rating": "5.0", "review": "Great pancakes!"},
            {"user_id": "1002", "recipe_id": "101", "date": "2020-01-11", "rating": "4.0", "review": "Fluffy and sweet."},
            {"user_id": "1003", "recipe_id": "201", "date": "2020-02-10", "rating": "5.0", "review": "Best stew ever."},
            {"user_id": "1004", "recipe_id": "301", "date": "2020-03-10", "rating": "5.0", "review": "Super chocolaty."},
            {"user_id": "1005", "recipe_id": "401", "date": "2020-04-10", "rating": "4.0", "review": "Crowd pleaser dip."},
            # Unmatched interactions (recipe IDs not in sample)
            {"user_id": "9991", "recipe_id": "99999", "date": "2020-06-01", "rating": "1.0", "review": "Ghost recipe review."},
            {"user_id": "9992", "recipe_id": "88888", "date": "2020-06-02", "rating": "2.0", "review": "Another ghost review."},
        ]

        with open(self.interactions_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.interaction_headers)
            writer.writeheader()
            for i in self.synthetic_interactions:
                writer.writerow(i)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_foodcom_sampler_determinism_and_output_preservation(self):
        # Run 1
        out1 = Path(self.test_dir) / "out1"
        sampler1 = FoodComSampler(self.source_dir, output_dir=out1, limit=4, seed=42)
        rep1 = sampler1.run(dry_run=False)

        # Run 2 with identical seed
        out2 = Path(self.test_dir) / "out2"
        sampler2 = FoodComSampler(self.source_dir, output_dir=out2, limit=4, seed=42)
        rep2 = sampler2.run(dry_run=False)

        # Verify determinism
        self.assertEqual(rep1.actual_sample_size, 4)
        self.assertEqual(rep2.actual_sample_size, 4)
        self.assertEqual(
            rep1.output_files["RAW_recipes.csv"]["sha256_checksum"],
            rep2.output_files["RAW_recipes.csv"]["sha256_checksum"],
        )
        self.assertEqual(
            rep1.output_files["RAW_interactions.csv"]["sha256_checksum"],
            rep2.output_files["RAW_interactions.csv"]["sha256_checksum"],
        )

        # Verify headers preserved
        with open(out1 / "RAW_recipes.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.assertEqual(headers, self.recipe_headers)

        # Verify malformed row was rejected (scanned 8, accepted 7, rejected 1)
        self.assertEqual(rep1.source_rows_scanned, 8)
        self.assertEqual(rep1.valid_rows, 7)
        self.assertEqual(rep1.rejected_rows, 1)

    def test_foodcom_interaction_filtering_referential_integrity(self):
        out = Path(self.test_dir) / "out_inter"
        sampler = FoodComSampler(self.source_dir, output_dir=out, limit=3, seed=42)
        report = sampler.run(dry_run=False)

        # Read selected recipe IDs
        selected_ids = set()
        with open(out / "RAW_recipes.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                selected_ids.add(row["id"].strip())

        self.assertEqual(len(selected_ids), 3)

        # Read output interactions
        retained_inter_recipes = set()
        with open(out / "RAW_interactions.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r_id = row["recipe_id"].strip()
                # Crucial assertion: NO unmatched interaction should ever exist
                self.assertIn(r_id, selected_ids)
                retained_inter_recipes.add(r_id)

        # Ghost IDs 99999 and 88888 must never be in retained interactions
        self.assertNotIn("99999", retained_inter_recipes)
        self.assertNotIn("88888", retained_inter_recipes)

        # Verify interaction stats in report
        self.assertEqual(report.interaction_stats["interactions_scanned"], 7)
        self.assertEqual(
            report.interaction_stats["interactions_retained"],
            report.output_files["RAW_interactions.csv"]["row_count"],
        )

    def test_foodcom_sampler_dry_run_creates_no_files(self):
        dry_out = Path(self.test_dir) / "dry_out"
        sampler = FoodComSampler(self.source_dir, output_dir=dry_out, limit=5, seed=42)
        report = sampler.run(dry_run=True)

        self.assertTrue(report.dry_run)
        self.assertEqual(report.actual_sample_size, 5)
        self.assertEqual(report.valid_rows, 7)
        # Ensure no output directory or CSV files were created
        self.assertFalse((dry_out / "RAW_recipes.csv").exists())
        self.assertFalse((dry_out / "RAW_interactions.csv").exists())
        self.assertFalse((dry_out / "sampling_report.json").exists())

    def test_foodcom_sampler_sample_greater_than_population(self):
        out = Path(self.test_dir) / "out_all"
        sampler = FoodComSampler(self.source_dir, output_dir=out, limit=500, seed=42)
        report = sampler.run(dry_run=False)

        # Total valid recipes in fixture is 7, so all 7 should be returned
        self.assertEqual(report.actual_sample_size, 7)
        self.assertEqual(report.valid_rows, 7)

    def test_foodcom_sampler_from_zip(self):
        # Create ZIP archive containing RAW_recipes.csv and RAW_interactions.csv
        zip_path = Path(self.test_dir) / "foodcom_fixture.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.write(self.recipes_csv, arcname="RAW_recipes.csv")
            z.write(self.interactions_csv, arcname="RAW_interactions.csv")

        out = Path(self.test_dir) / "out_zip"
        sampler = FoodComSampler(zip_path, output_dir=out, limit=4, seed=42)
        report = sampler.run(dry_run=False)

        self.assertEqual(report.actual_sample_size, 4)
        self.assertTrue((out / "RAW_recipes.csv").exists())
        self.assertTrue((out / "RAW_interactions.csv").exists())
        self.assertTrue((out / "sampling_report.json").exists())

    def test_foodcom_sampler_cleanup_on_error(self):
        out = Path(self.test_dir) / "out_err"
        sampler = FoodComSampler(self.source_dir, output_dir=out, limit=4, seed=42)

        # Mock an exception during interaction streaming to test cleanup
        with patch.object(sampler.source, "open_csv_stream", side_effect=IOError("Simulated disk error")):
            with self.assertRaises(IOError):
                sampler.run(dry_run=False)

        # Partial files should be unlinked
        self.assertFalse((out / "RAW_recipes.csv").exists())

    def test_foodcom_sampler_duplicate_id_rejection(self):
        # Append a duplicate recipe with id='101'
        dup_row = {
            "name": "Duplicate Pancakes",
            "id": "101",  # Same as Classic Fluffy Pancakes
            "minutes": "15",
            "contributor_id": "99",
            "submitted": "2020-01-05",
            "tags": "['breakfast']",
            "nutrition": "[300.0, 10.0, 5.0, 15.0, 8.0, 4.0, 25.0]",
            "n_steps": "1",
            "steps": "['Cook.']",
            "description": "Duplicate id must be rejected.",
            "ingredients": "['flour']",
            "n_ingredients": "1",
        }
        with open(self.recipes_csv, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.recipe_headers)
            writer.writerow(dup_row)

        out = Path(self.test_dir) / "out_dup"
        sampler = FoodComSampler(self.source_dir, output_dir=out, limit=10, seed=42)
        report = sampler.run(dry_run=False)

        # Total scanned should be 9, valid 7, rejected 2 (invalid_id_999 + duplicate 101)
        self.assertEqual(report.source_rows_scanned, 9)
        self.assertEqual(report.valid_rows, 7)
        self.assertEqual(report.rejected_rows, 2)

        # Output recipes must have strictly unique IDs
        selected_ids = []
        with open(out / "RAW_recipes.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                selected_ids.append(r["id"])
        self.assertEqual(len(selected_ids), len(set(selected_ids)))

    def test_subprocess_foodcom_cross_process_determinism(self):
        """Verify cross-process determinism when running with different PYTHONHASHSEED values."""
        out_dirs = [
            Path(self.test_dir) / "proc_rand",
            Path(self.test_dir) / "proc_zero",
            Path(self.test_dir) / "proc_fixed",
        ]
        seeds_env = ["random", "0", "54321"]
        checksums = []

        runner_code = (
            "import sys\n"
            "from pathlib import Path\n"
            "from ingestion.sampling.foodcom_sampler import FoodComSampler\n"
            "source_dir = Path(sys.argv[1])\n"
            "out_dir = Path(sys.argv[2])\n"
            "seed = int(sys.argv[3])\n"
            "sampler = FoodComSampler(source_dir, output_dir=out_dir, limit=4, seed=seed)\n"
            "report = sampler.run(dry_run=False)\n"
            "print(report.output_files['RAW_recipes.csv']['sha256_checksum'])\n"
        )

        for out_dir, hash_seed in zip(out_dirs, seeds_env):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = hash_seed
            env["PYTHONPATH"] = str(Path(".").resolve())
            proc = subprocess.run(
                [sys.executable, "-c", runner_code, str(self.source_dir), str(out_dir), "42"],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            sha = proc.stdout.strip().splitlines()[-1]
            checksums.append(sha)

        # Output must be identical across processes regardless of PYTHONHASHSEED
        self.assertEqual(checksums[0], checksums[1])
        self.assertEqual(checksums[1], checksums[2])

        # Different user seed must produce different checksum
        out_diff = Path(self.test_dir) / "proc_diff_seed"
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = "random"
        env["PYTHONPATH"] = str(Path(".").resolve())
        proc_diff = subprocess.run(
            [sys.executable, "-c", runner_code, str(self.source_dir), str(out_diff), "999"],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        sha_diff = proc_diff.stdout.strip().splitlines()[-1]
        self.assertNotEqual(sha_diff, checksums[0])


class TestRecipeNLGCategorization(unittest.TestCase):
    """Tests for RecipeNLG provenance, NER richness, and directions status categorization."""

    def test_classify_source_origin(self):
        # Gathered variants and encoding
        self.assertEqual(classify_source_origin("Gathered"), "Gathered")
        self.assertEqual(classify_source_origin("gathered"), "Gathered")
        self.assertEqual(classify_source_origin("1"), "Gathered")

        # Recipes1M variants and encoding
        self.assertEqual(classify_source_origin("Recipes1M"), "Recipes1M")
        self.assertEqual(classify_source_origin("recipes1m"), "Recipes1M")
        self.assertEqual(classify_source_origin("recipe1m"), "Recipes1M")
        self.assertEqual(classify_source_origin("0"), "Recipes1M")

        # Unknown / Unrecognized / None / Empty
        self.assertEqual(classify_source_origin("allrecipes.com"), "Unknown")
        self.assertEqual(classify_source_origin("custom"), "Unknown")
        self.assertEqual(classify_source_origin("2"), "Unknown")
        self.assertEqual(classify_source_origin(""), "Unknown")
        self.assertEqual(classify_source_origin(None), "Unknown")

    def test_source_classification_independent_of_recipe_id(self):
        """Verify source origin is strictly derived from 'source' column and never from recipe id."""
        # Low ID (< 1.6M) with Gathered source
        row_low_gathered = {"id": "0", "source": "Gathered", "NER": "['flour']", "directions": "['mix']"}
        self.assertEqual(classify_source_origin(row_low_gathered["source"]), "Gathered")
        self.assertTrue(determine_recipenlg_stratum(row_low_gathered).startswith("Gathered__"))

        # High ID (>= 1.6M) with Recipes1M source
        row_high_recipes1m = {"id": "2000000", "source": "Recipes1M", "NER": "['flour']", "directions": "['mix']"}
        self.assertEqual(classify_source_origin(row_high_recipes1m["source"]), "Recipes1M")
        self.assertTrue(determine_recipenlg_stratum(row_high_recipes1m).startswith("Recipes1M__"))

        # Intermediate threshold ID with unknown source
        row_threshold_unknown = {"id": "1600000", "source": "custom_site", "NER": "['flour']", "directions": "['mix']"}
        self.assertEqual(classify_source_origin(row_threshold_unknown["source"]), "Unknown")
        self.assertTrue(determine_recipenlg_stratum(row_threshold_unknown).startswith("Unknown__"))

    def test_classify_ner_richness(self):
        self.assertEqual(classify_ner_richness(None), "ner_0")
        self.assertEqual(classify_ner_richness("[]"), "ner_0")
        self.assertEqual(classify_ner_richness("invalid_json"), "ner_0")
        self.assertEqual(classify_ner_richness("['flour', 'sugar']"), "ner_1_3")
        self.assertEqual(classify_ner_richness("['1', '2', '3', '4', '5']"), "ner_4_8")
        self.assertEqual(classify_ner_richness("['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']"), "ner_gt_8")

    def test_classify_directions_status(self):
        self.assertEqual(classify_directions_status("['Step 1', 'Step 2']"), "directions_usable")
        self.assertEqual(classify_directions_status("[]"), "directions_empty")
        self.assertEqual(classify_directions_status(None), "directions_empty")
        self.assertEqual(classify_directions_status("unparseable"), "directions_empty")

    def test_determine_recipenlg_stratum_composite(self):
        row = {
            "source": "Gathered",
            "NER": "['garlic', 'onion', 'olive oil']",
            "directions": "['Saute onions.', 'Add garlic.']",
        }
        self.assertEqual(determine_recipenlg_stratum(row), "Gathered__ner_1_3__directions_usable")


class TestRecipeNLGSamplerPipeline(unittest.TestCase):
    """Tests for the end-to-end RecipeNLG sampling pipeline."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.test_dir) / "source"
        self.output_dir = Path(self.test_dir) / "output"
        self.source_dir.mkdir(parents=True)

        self.dataset_csv = self.source_dir / "full_dataset.csv"
        self.headers = ["id", "title", "ingredients", "directions", "link", "source", "NER"]

        # Synthetic RecipeNLG records across strata
        self.synthetic_recipes = [
            {
                "id": "0",
                "title": "Grandma's Cinnamon Rolls",
                "ingredients": "['2 cups flour', '1 tsp yeast', '1/2 cup sugar', '1 tbsp cinnamon']",
                "directions": "['Roll out dough.', 'Sprinkle cinnamon.', 'Bake 20 min.']",
                "link": "www.gathered.com/rolls",
                "source": "Gathered",
                "NER": "['flour', 'yeast', 'sugar', 'cinnamon']",
            },
            {
                "id": "1",
                "title": "Simple French Toast",
                "ingredients": "['4 slices bread', '2 eggs', '1/4 cup milk']",
                "directions": "['Dip bread.', 'Fry in butter.']",
                "link": "www.recipes1m.com/toast",
                "source": "Recipes1M",
                "NER": "['bread', 'eggs', 'milk']",
            },
            {
                "id": "2",
                "title": "Slow Cooker Pot Roast",
                "ingredients": "['3 lb chuck roast', '1 packet onion soup mix', '1 can cream of mushroom soup']",
                "directions": "['Place in cooker.', 'Cook on low 8 hours.']",
                "link": "www.gathered.com/roast",
                "source": "Gathered",
                "NER": "['chuck roast', 'onion soup mix', 'cream of mushroom soup']",
            },
            {
                "id": "3",
                "title": "Minimalist Green Salad",
                "ingredients": "['4 cups mixed greens', '2 tbsp olive oil', '1 tbsp lemon juice']",
                "directions": "['Toss greens with dressing.']",
                "link": "www.recipes1m.com/salad",
                "source": "Recipes1M",
                "NER": "['mixed greens', 'olive oil', 'lemon juice']",
            },
            {
                "id": "4",
                "title": "Recipe Without Directions",
                "ingredients": "['1 cup rice', '2 cups water']",
                "directions": "[]",  # Empty directions
                "link": "www.unknown.com/rice",
                "source": "CustomDomain",
                "NER": "['rice', 'water']",
            },
            {
                "id": "5",
                "title": "Complex Gumbo with Rich NER",
                "ingredients": "['1 lb shrimp', '1 lb sausage', '1 cup celery', '1 cup onion', '1 cup bell pepper', '1/2 cup flour', '1/2 cup oil', '4 cups broth', '2 bay leaves', '1 tsp thyme']",
                "directions": "['Make roux.', 'Add trinity.', 'Simmer gumbo.']",
                "link": "www.gathered.com/gumbo",
                "source": "Gathered",
                "NER": "['shrimp', 'sausage', 'celery', 'onion', 'bell pepper', 'flour', 'oil', 'broth', 'bay leaves', 'thyme']",
            },
            {
                # Malformed row (missing mandatory title)
                "id": "6",
                "title": "",
                "ingredients": "['salt']",
                "directions": "['Eat salt.']",
                "link": "www.bad.com",
                "source": "Gathered",
                "NER": "['salt']",
            },
        ]

        with open(self.dataset_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.headers)
            writer.writeheader()
            for r in self.synthetic_recipes:
                writer.writerow(r)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_recipenlg_sampler_determinism_and_preservation(self):
        out1 = Path(self.test_dir) / "out1"
        sampler1 = RecipeNLGSampler(self.dataset_csv, output_dir=out1, limit=3, seed=42)
        rep1 = sampler1.run(dry_run=False)

        out2 = Path(self.test_dir) / "out2"
        sampler2 = RecipeNLGSampler(self.dataset_csv, output_dir=out2, limit=3, seed=42)
        rep2 = sampler2.run(dry_run=False)

        self.assertEqual(rep1.actual_sample_size, 3)
        self.assertEqual(rep2.actual_sample_size, 3)
        self.assertEqual(
            rep1.output_files["full_dataset.csv"]["sha256_checksum"],
            rep2.output_files["full_dataset.csv"]["sha256_checksum"],
        )

        # Verify headers preserved
        with open(out1 / "full_dataset.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            self.assertEqual(headers, self.headers)

        # Scanned 7, valid 6, rejected 1 (missing title)
        self.assertEqual(rep1.source_rows_scanned, 7)
        self.assertEqual(rep1.valid_rows, 6)
        self.assertEqual(rep1.rejected_rows, 1)

    def test_recipenlg_sampler_different_seeds(self):
        # With a larger fixture or different seed on limit=2 from 6 rows
        out1 = Path(self.test_dir) / "seed1"
        out2 = Path(self.test_dir) / "seed2"

        sampler1 = RecipeNLGSampler(self.dataset_csv, output_dir=out1, limit=2, seed=1)
        rep1 = sampler1.run(dry_run=False)

        sampler2 = RecipeNLGSampler(self.dataset_csv, output_dir=out2, limit=2, seed=99999)
        rep2 = sampler2.run(dry_run=False)

        self.assertEqual(rep1.actual_sample_size, 2)
        self.assertEqual(rep2.actual_sample_size, 2)

    def test_recipenlg_sampler_dry_run(self):
        dry_out = Path(self.test_dir) / "dry_recipenlg"
        sampler = RecipeNLGSampler(self.dataset_csv, output_dir=dry_out, limit=4, seed=42)
        report = sampler.run(dry_run=True)

        self.assertTrue(report.dry_run)
        self.assertEqual(report.actual_sample_size, 4)
        self.assertEqual(report.valid_rows, 6)
        self.assertFalse((dry_out / "full_dataset.csv").exists())
        self.assertFalse((dry_out / "sampling_report.json").exists())

    def test_recipenlg_sampler_from_zip(self):
        zip_path = Path(self.test_dir) / "recipenlg_fixture.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.write(self.dataset_csv, arcname="full_dataset.csv")

        out = Path(self.test_dir) / "out_zip_nlg"
        sampler = RecipeNLGSampler(zip_path, output_dir=out, limit=3, seed=42)
        report = sampler.run(dry_run=False)

        self.assertEqual(report.actual_sample_size, 3)
        self.assertTrue((out / "full_dataset.csv").exists())
        self.assertTrue((out / "sampling_report.json").exists())

    def test_recipenlg_sampler_report_json_accuracy(self):
        out = Path(self.test_dir) / "out_report"
        sampler = RecipeNLGSampler(self.dataset_csv, output_dir=out, limit=3, seed=42)
        report = sampler.run(dry_run=False)

        report_json = out / "sampling_report.json"
        self.assertTrue(report_json.exists())

        with open(report_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["dataset"], "recipenlg")
        self.assertEqual(data["seed"], 42)
        self.assertEqual(data["requested_sample_size"], 3)
        self.assertEqual(data["actual_sample_size"], 3)
        self.assertEqual(data["valid_rows"], 6)
        self.assertEqual(data["rejected_rows"], 1)
        self.assertIn("full_dataset.csv", data["output_files"])
        self.assertIn("sha256_checksum", data["output_files"]["full_dataset.csv"])

    def test_subprocess_recipenlg_cross_process_determinism(self):
        """Verify RecipeNLG cross-process determinism when running with different PYTHONHASHSEED values."""
        out_dirs = [
            Path(self.test_dir) / "proc_rand_nlg",
            Path(self.test_dir) / "proc_zero_nlg",
            Path(self.test_dir) / "proc_fixed_nlg",
        ]
        seeds_env = ["random", "0", "54321"]
        checksums = []

        runner_code = (
            "import sys\n"
            "from pathlib import Path\n"
            "from ingestion.sampling.recipenlg_sampler import RecipeNLGSampler\n"
            "csv_path = Path(sys.argv[1])\n"
            "out_dir = Path(sys.argv[2])\n"
            "seed = int(sys.argv[3])\n"
            "sampler = RecipeNLGSampler(csv_path, output_dir=out_dir, limit=3, seed=seed)\n"
            "report = sampler.run(dry_run=False)\n"
            "print(report.output_files['full_dataset.csv']['sha256_checksum'])\n"
        )

        for out_dir, hash_seed in zip(out_dirs, seeds_env):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = hash_seed
            env["PYTHONPATH"] = str(Path(".").resolve())
            proc = subprocess.run(
                [sys.executable, "-c", runner_code, str(self.dataset_csv), str(out_dir), "42"],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            sha = proc.stdout.strip().splitlines()[-1]
            checksums.append(sha)

        # Output must be identical across processes regardless of PYTHONHASHSEED
        self.assertEqual(checksums[0], checksums[1])
        self.assertEqual(checksums[1], checksums[2])

        # Different user seed must produce different checksum
        out_diff = Path(self.test_dir) / "proc_diff_seed_nlg"
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = "random"
        env["PYTHONPATH"] = str(Path(".").resolve())
        proc_diff = subprocess.run(
            [sys.executable, "-c", runner_code, str(self.dataset_csv), str(out_diff), "999"],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        sha_diff = proc_diff.stdout.strip().splitlines()[-1]
        self.assertNotEqual(sha_diff, checksums[0])


class TestSamplingIntegrationWithImporters(unittest.TestCase):
    """Verifies that sampled outputs can be consumed directly by existing dataset importers."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_foodcom_sampled_output_consumed_by_foodcom_importer(self):
        # 1. Generate Food.com sample
        source_dir = Path(self.test_dir) / "fc_source"
        sample_dir = Path(self.test_dir) / "fc_sample"
        source_dir.mkdir(parents=True)

        recipes_csv = source_dir / "RAW_recipes.csv"
        interactions_csv = source_dir / "RAW_interactions.csv"

        headers = [
            "name", "id", "minutes", "contributor_id", "submitted",
            "tags", "nutrition", "n_steps", "steps", "description",
            "ingredients", "n_ingredients"
        ]
        with open(recipes_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerow({
                "name": "Dev Sample Recipe",
                "id": "777",
                "minutes": "20",
                "contributor_id": "1",
                "submitted": "2020-01-01",
                "tags": "['dinner']",
                "nutrition": "[400.0, 10.0, 5.0, 20.0, 15.0, 4.0, 30.0]",
                "n_steps": "1",
                "steps": "['Cook thoroughly.']",
                "description": "Dev recipe.",
                "ingredients": "['chicken', 'rice']",
                "n_ingredients": "2",
            })

        inter_headers = ["user_id", "recipe_id", "date", "rating", "review"]
        with open(interactions_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=inter_headers)
            writer.writeheader()
            writer.writerow({
                "user_id": "1",
                "recipe_id": "777",
                "date": "2020-01-02",
                "rating": "5.0",
                "review": "Excellent!",
            })

        # Run FoodComSampler
        sampler = FoodComSampler(source_dir, output_dir=sample_dir, limit=1, seed=42)
        sample_rep = sampler.run(dry_run=False)
        self.assertEqual(sample_rep.actual_sample_size, 1)

        # 2. Feed sampled output directory to FoodComImporter dry-run
        importer = FoodComImporter(source_path=sample_dir, component="all", dry_run=True)
        import_rep = importer.run()

        # The importer should validate 1 recipe and 1 interaction with zero rejections
        self.assertEqual(import_rep.status, "dry_run_passed")
        self.assertEqual(import_rep.recipe_metrics["accepted_recipes"], 1)
        self.assertEqual(import_rep.interaction_metrics["valid_ratings"], 1)
        self.assertEqual(import_rep.recipe_metrics["rejected_recipes"], 0)

    def test_recipenlg_sampled_output_consumed_by_recipenlg_importer(self):
        # 1. Generate RecipeNLG sample
        source_dir = Path(self.test_dir) / "nlg_source"
        sample_dir = Path(self.test_dir) / "nlg_sample"
        source_dir.mkdir(parents=True)

        csv_path = source_dir / "full_dataset.csv"
        headers = ["id", "title", "ingredients", "directions", "link", "source", "NER"]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerow({
                "id": "0",
                "title": "Dev Sample RecipeNLG",
                "ingredients": "['2 cups flour', '1 cup milk']",
                "directions": "['Mix ingredients.', 'Bake at 350F.']",
                "link": "www.gathered.com/test",
                "source": "Gathered",
                "NER": "['flour', 'milk']",
            })

        # Run RecipeNLGSampler
        sampler = RecipeNLGSampler(csv_path, output_dir=sample_dir, limit=1, seed=42)
        sample_rep = sampler.run(dry_run=False)
        self.assertEqual(sample_rep.actual_sample_size, 1)

        # 2. Feed sampled output CSV to RecipeNLGImporter dry-run
        sampled_csv = sample_dir / "full_dataset.csv"
        importer = RecipeNLGImporter(source_path=sampled_csv, dry_run=True)
        import_rep = importer.run()

        self.assertEqual(import_rep.status, "dry_run_passed")
        self.assertEqual(import_rep.metrics["accepted_recipes"], 1)
        self.assertEqual(import_rep.metrics["rejected_rows"], 0)


if __name__ == "__main__":
    unittest.main()
