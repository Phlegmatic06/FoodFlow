"""Unit tests for Food.com Recipes & Interactions ingestion pipeline using synthetic fixtures.

Note: All test datasets utilized herein are synthetic unit-test mocks created solely
for validating parser, schema, error-handling, and aggregation logic. They do NOT
represent official Food.com or BERD platform records.
"""

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ingestion.datasets.foodcom.importer import FoodComImporter, FoodComReport
from ingestion.datasets.foodcom.loader import FoodComLoader
from ingestion.datasets.foodcom.parser import (
    FoodComParseError,
    FoodComSource,
    clean_text,
    parse_date,
    parse_nutrition_array,
    parse_time_minutes,
    safe_parse_python_list,
)
from ingestion.datasets.foodcom.ratings import RatingsAggregationMetrics, RatingsAggregator
from ingestion.datasets.foodcom.validator import (
    FoodComValidationError,
    UnmatchedRecipeError,
    ValidatedInteraction,
    ValidatedRecipe,
    validate_headers,
    validate_interaction_record,
    validate_recipe_record,
)
from ingestion.manifest import (
    STATUS_COMPLETED,
    STATUS_DOWNLOADED,
    STATUS_NOT_DOWNLOADED,
    STATUS_PARTIALLY_IMPORTED,
    STATUS_VERIFIED,
    create_initial_manifest,
    load_manifest,
    record_verified_file,
    save_manifest,
)


class TestFoodComParser(unittest.TestCase):
    """Test AST literal parsing, nutrition arrays, time minutes, and data coercion."""

    def test_safe_parse_python_list_valid(self):
        # Valid list of strings
        res = safe_parse_python_list("['apple', 'banana', 'flour']")
        self.assertEqual(res, ["apple", "banana", "flour"])

        # Valid list of numbers
        res = safe_parse_python_list("[1, 2, 3]")
        self.assertEqual(res, [1, 2, 3])

        # Empty string / None returns empty list
        self.assertEqual(safe_parse_python_list(None), [])
        self.assertEqual(safe_parse_python_list(""), [])
        self.assertEqual(safe_parse_python_list("   "), [])
        self.assertEqual(safe_parse_python_list("[]"), [])

        # Whitespace and newlines within brackets
        res = safe_parse_python_list("[\n  'line1',\n  'line2'\n]")
        self.assertEqual(res, ["line1", "line2"])

    def test_safe_parse_python_list_security_and_syntax(self):
        # Non-list syntax rejected
        with self.assertRaises(FoodComParseError):
            safe_parse_python_list("hello world")

        with self.assertRaises(FoodComParseError):
            safe_parse_python_list("{'key': 'value'}")

        with self.assertRaises(FoodComParseError):
            safe_parse_python_list("(1, 2, 3)")

        # Code execution and injection attempts rejected
        with self.assertRaises(FoodComParseError):
            safe_parse_python_list("__import__('os').system('dir')")

        with self.assertRaises(FoodComParseError):
            safe_parse_python_list("[open('fake').read()]")

        with self.assertRaises(FoodComParseError):
            safe_parse_python_list("[x for x in range(10)]")

        # Unbalanced syntax
        with self.assertRaises(FoodComParseError):
            safe_parse_python_list("['unclosed string")

    def test_parse_nutrition_array(self):
        # Valid 7-element float array
        raw = "[250.5, 10.0, 15.2, 50.0, 12.0, 4.5, 30.0]"
        nut = parse_nutrition_array(raw)
        self.assertEqual(len(nut), 7)
        self.assertEqual(nut[0], 250.5)
        self.assertEqual(nut[6], 30.0)

        # Valid integer coercion to floats
        raw_int = "[200, 5, 10, 8, 4, 2, 25]"
        nut_int = parse_nutrition_array(raw_int)
        self.assertEqual(nut_int, (200.0, 5.0, 10.0, 8.0, 4.0, 2.0, 25.0))

        # Non-7 element arrays rejected
        with self.assertRaises(FoodComParseError):
            parse_nutrition_array("[200.0, 10.0, 5.0]")  # 3 elements

        with self.assertRaises(FoodComParseError):
            parse_nutrition_array("[1, 2, 3, 4, 5, 6, 7, 8]")  # 8 elements

        # Negative numbers rejected
        with self.assertRaises(FoodComParseError):
            parse_nutrition_array("[200.0, -5.0, 10.0, 8.0, 4.0, 2.0, 25.0]")

        # Non-numeric elements rejected
        with self.assertRaises(FoodComParseError):
            parse_nutrition_array("[200.0, 'bad', 10.0, 8.0, 4.0, 2.0, 25.0]")

        # Empty / None rejected
        with self.assertRaises(FoodComParseError):
            parse_nutrition_array(None)

    def test_parse_time_minutes(self):
        # Standard positive minutes
        self.assertEqual(parse_time_minutes("45"), 45)
        self.assertEqual(parse_time_minutes("0"), 0)
        self.assertEqual(parse_time_minutes(120), 120)

        # Empty or None -> None
        self.assertIsNone(parse_time_minutes(None))
        self.assertIsNone(parse_time_minutes(""))
        self.assertIsNone(parse_time_minutes("   "))

        # Negative minutes -> None
        self.assertIsNone(parse_time_minutes("-10"))

        # Sentinel / Absurd values mapped to None (> 43,200 min / 30 days)
        self.assertIsNone(parse_time_minutes("43201"))
        self.assertIsNone(parse_time_minutes("2147483647"))

        # Non-numeric -> None
        self.assertIsNone(parse_time_minutes("quick"))

    def test_clean_text_and_date(self):
        self.assertEqual(clean_text("  Chicken Soup  "), "Chicken Soup")
        self.assertIsNone(clean_text(None))
        self.assertIsNone(clean_text("   \t\n  "))
        self.assertEqual(clean_text("Clean\x00Text"), "CleanText")

        self.assertEqual(parse_date("2020-05-15"), "2020-05-15")
        self.assertEqual(parse_date("2020-05-15 14:30:00"), "2020-05-15")
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date("not-a-date"))


class TestFoodComValidator(unittest.TestCase):
    """Test header verification and record-level validation rules."""

    def test_header_validation(self):
        recipe_headers = [
            "name", "id", "minutes", "contributor_id", "submitted",
            "tags", "nutrition", "n_steps", "steps", "description",
            "ingredients", "n_ingredients",
        ]
        ok, missing = validate_headers("raw_recipes.csv", recipe_headers)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

        # Missing 'nutrition'
        bad_recipe_headers = ["name", "id", "ingredients", "steps"]
        ok, missing = validate_headers("raw_recipes.csv", bad_recipe_headers)
        self.assertFalse(ok)
        self.assertIn("nutrition", missing)

        # Interactions header validation
        inter_headers = ["user_id", "recipe_id", "date", "rating", "review"]
        ok, missing = validate_headers("raw_interactions.csv", inter_headers)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

        # Missing 'rating'
        bad_inter_headers = ["user_id", "recipe_id", "review"]
        ok, missing = validate_headers("raw_interactions.csv", bad_inter_headers)
        self.assertFalse(ok)
        self.assertIn("rating", missing)

    def test_validate_recipe_record(self):
        valid_row = {
            "name": "Classic Apple Pie",
            "id": "137739",
            "minutes": "60",
            "submitted": "2005-09-16",
            "tags": "['dessert', 'apple', 'baking', 'DESSERT']",
            "nutrition": "[350.0, 15.0, 25.0, 10.0, 4.0, 5.0, 45.0]",
            "steps": "['Mix crust ingredients', 'Fill with apples', 'Bake at 375F']",
            "description": "A delicious classic apple pie recipe.",
            "ingredients": "['apples', 'flour', 'butter', 'sugar', 'cinnamon']",
        }

        recipe = validate_recipe_record(valid_row, line_number=2)
        self.assertEqual(recipe.id, "rcp_foodcom_137739")
        self.assertEqual(recipe.source_id, "137739")
        self.assertEqual(recipe.title, "Classic Apple Pie")
        self.assertEqual(recipe.total_time_minutes, 60)
        self.assertIsNone(recipe.prep_time_minutes)
        self.assertIsNone(recipe.cook_time_minutes)
        self.assertEqual(recipe.calories, 350.0)

        # Tags should be lowercased and deduplicated: 'dessert', 'apple', 'baking'
        self.assertEqual(len(recipe.tags), 3)
        self.assertIn("dessert", recipe.tags)
        self.assertIn("apple", recipe.tags)
        self.assertIn("baking", recipe.tags)

        # Ingredients and steps count
        self.assertEqual(len(recipe.ingredients), 5)
        self.assertEqual(len(recipe.instructions), 3)

    def test_validate_recipe_record_edge_cases(self):
        # Title truncation to 512 chars
        long_title = "A" * 600
        row = {
            "name": long_title,
            "id": "2001",
            "minutes": "30",
            "tags": "['tag1']",
            "nutrition": "[100, 1, 2, 3, 4, 5, 6]",
            "steps": "['step 1']",
            "ingredients": "['flour']",
        }
        recipe = validate_recipe_record(row, line_number=3)
        self.assertEqual(len(recipe.title), 512)

        # Invalid recipe ID raises error
        bad_id_row = dict(row, id="not_a_number")
        with self.assertRaises(FoodComValidationError):
            validate_recipe_record(bad_id_row, line_number=4)

        # Empty ingredients list raises error
        no_ing_row = dict(row, ingredients="[]")
        with self.assertRaises(FoodComValidationError):
            validate_recipe_record(no_ing_row, line_number=5)

        # Empty steps list raises error
        no_steps_row = dict(row, steps="[]")
        with self.assertRaises(FoodComValidationError):
            validate_recipe_record(no_steps_row, line_number=6)

    def test_validate_interaction_record(self):
        valid_row = {
            "user_id": "4242",
            "recipe_id": "137739",
            "date": "2006-03-01",
            "rating": "5",
            "review": "Excellent pie!",
        }

        # Valid interaction with known recipe
        inter = validate_interaction_record(valid_row, line_number=2, known_recipe_ids={"rcp_foodcom_137739"})
        self.assertEqual(inter.recipe_id, "rcp_foodcom_137739")
        self.assertEqual(inter.source_id, "137739")
        self.assertEqual(inter.rating, 5.0)

        # Rating 0 (unrated review) rejected
        unrated_row = dict(valid_row, rating="0")
        with self.assertRaises(FoodComValidationError):
            validate_interaction_record(unrated_row, line_number=3)

        # Rating out of range (> 5.0) rejected
        high_rating_row = dict(valid_row, rating="6")
        with self.assertRaises(FoodComValidationError):
            validate_interaction_record(high_rating_row, line_number=4)

        # Rating negative rejected
        neg_rating_row = dict(valid_row, rating="-1")
        with self.assertRaises(FoodComValidationError):
            validate_interaction_record(neg_rating_row, line_number=5)

        # Unmatched recipe ID raises UnmatchedRecipeError when known IDs given
        with self.assertRaises(UnmatchedRecipeError):
            validate_interaction_record(valid_row, line_number=6, known_recipe_ids={"rcp_foodcom_999999"})


class TestFoodComSourceAndZipHandling(unittest.TestCase):
    """Test streaming file reader for both uncompressed directories and ZIP archives."""

    def test_directory_source(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "RAW_recipes.csv").write_text("name,id,ingredients,steps,nutrition\n", encoding="utf-8")
            (tmp_path / "RAW_interactions.csv").write_text("recipe_id,rating\n", encoding="utf-8")

            source = FoodComSource(tmp_path)
            self.assertFalse(source.is_zip)
            self.assertTrue(source.has_file("raw_recipes.csv"))
            self.assertTrue(source.has_file("raw_interactions.csv"))
            self.assertEqual(source.inspect_headers("raw_recipes.csv"), ["name", "id", "ingredients", "steps", "nutrition"])

    def test_zip_source(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "foodcom.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("nested/RAW_recipes.csv", "name,id,ingredients,steps,nutrition\n")
                zf.writestr("nested/RAW_interactions.csv", "recipe_id,rating\n")

            source = FoodComSource(zip_path)
            self.assertTrue(source.is_zip)
            self.assertTrue(source.has_file("raw_recipes.csv"))
            self.assertTrue(source.has_file("raw_interactions.csv"))
            self.assertEqual(source.inspect_headers("raw_recipes.csv"), ["name", "id", "ingredients", "steps", "nutrition"])

    def test_missing_file_raises_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = FoodComSource(Path(tmp_dir))
            with self.assertRaises(FileNotFoundError):
                list(source.open_csv_stream("raw_recipes.csv"))


class TestRatingsAggregator(unittest.TestCase):
    """Test memory-bounded ratings aggregation and staged SQL queries."""

    def test_dry_run_aggregation(self):
        aggregator = RatingsAggregator(connection=None, batch_size=2)
        stream = [
            (2, {"recipe_id": "101", "rating": "5"}),
            (3, {"recipe_id": "101", "rating": "4"}),
            (4, {"recipe_id": "101", "rating": "3"}),
            (5, {"recipe_id": "102", "rating": "5"}),
            (6, {"recipe_id": "102", "rating": "4"}),
        ]

        metrics = aggregator.process_interactions_stream(iter(stream), dry_run=True)
        self.assertEqual(metrics.valid_ratings, 5)
        self.assertEqual(metrics.updated_recipes_count, 2)

    def test_database_staging_queries(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        aggregator = RatingsAggregator(connection=mock_conn, batch_size=2)
        stream = [
            (2, {"recipe_id": "101", "rating": "5"}),
            (3, {"recipe_id": "102", "rating": "4"}),
        ]

        metrics = aggregator.process_interactions_stream(iter(stream), dry_run=False)
        self.assertEqual(metrics.valid_ratings, 2)

        # Check staging table setup
        executed_sqls = [call[0][0] for call in mock_cur.execute.call_args_list]
        self.assertTrue(any("CREATE TEMP TABLE IF NOT EXISTS temp_foodcom_ratings_staging" in sql for sql in executed_sqls))
        self.assertTrue(any("INSERT INTO recipe_catalog.recipe_ratings" in sql for sql in executed_sqls))
        self.assertTrue(any("DROP TABLE IF EXISTS temp_foodcom_ratings_staging" in sql for sql in executed_sqls))


class TestFoodComLoader(unittest.TestCase):
    """Test batch database loading, child row synchronization, and provenance auditing."""

    def test_load_recipes_batch_queries(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        loader = FoodComLoader(mock_conn)

        valid_recipes = [
            ValidatedRecipe(
                id="rcp_foodcom_101",
                source_id="101",
                source_dataset="food_com",
                title="Apple Crisp",
                description="Warm apple dessert",
                total_time_minutes=45,
                prep_time_minutes=None,
                cook_time_minutes=None,
                servings=None,
                cuisine=None,
                source_url="https://www.food.com/recipe/101",
                submitted_date="2020-01-01",
                ingredients=["sliced apples", "oats", "brown sugar"],
                instructions=["Slice apples", "Mix oats and sugar", "Bake at 350F"],
                tags=["dessert", "apples", "baking"],
                nutrition=(250.0, 10.0, 15.0, 5.0, 2.0, 3.0, 35.0),
            )
        ]

        canonical_map = {"apples": "uuid-apple-123"}
        counts = loader.load_recipes_batch(valid_recipes, canonical_map)

        self.assertEqual(counts["recipes"], 1)
        self.assertEqual(counts["recipe_ingredients"], 3)
        self.assertEqual(counts["recipe_instructions"], 3)
        self.assertEqual(counts["recipe_tags"], 3)
        self.assertEqual(counts["recipe_nutrition_raw"], 1)

        # Verify child row cleanup executed before re-insertion
        execute_sqls = [call[0][0] for call in mock_cur.execute.call_args_list]
        self.assertTrue(any("DELETE FROM recipe_catalog.recipe_ingredients" in sql for sql in execute_sqls))
        self.assertTrue(any("DELETE FROM recipe_catalog.recipe_instructions" in sql for sql in execute_sqls))
        self.assertTrue(any("DELETE FROM recipe_catalog.recipe_tags" in sql for sql in execute_sqls))

        # Verify executemany called for recipes and child records
        self.assertTrue(mock_cur.executemany.called)


class TestFoodComImporterDryRunAndManifest(unittest.TestCase):
    """Test full importer dry-run simulation and manifest tracking."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Write synthetic RAW_recipes.csv with proper double-quoted CSV fields
        (self.dir_path / "RAW_recipes.csv").write_text(
            'name,id,minutes,contributor_id,submitted,tags,nutrition,n_steps,steps,description,ingredients,n_ingredients\n'
            'Apple Crumble,5001,40,10,2020-01-01,"[\'dessert\', \'apple\']","[220.0, 8.0, 15.0, 4.0, 2.0, 3.0, 30.0]",2,"[\'Mix ingredients\', \'Bake 40 mins\']",Sweet crumble,"[\'apple\', \'oats\']",2\n'
            'Berry Smoothie,5002,10,11,2020-02-01,"[\'beverage\', \'healthy\']","[150.0, 1.0, 20.0, 2.0, 5.0, 0.5, 25.0]",2,"[\'Blend berries\', \'Serve cold\']",Quick drink,"[\'berries\', \'yogurt\']",2\n'
            'Malformed Recipe,invalid_id,10,12,2020-03-01,"[]","[100]",1,"[\'step\']",desc,"[\'item\']",1\n',  # Rejected ID & nutrition
            encoding="utf-8",
        )

        # Write synthetic RAW_interactions.csv
        (self.dir_path / "RAW_interactions.csv").write_text(
            "user_id,recipe_id,date,rating,review\n"
            "1001,5001,2020-05-01,5,Loved it!\n"
            "1002,5001,2020-05-02,4,Very good.\n"
            "1003,5002,2020-05-03,5,Refreshing.\n"
            "1004,5002,2020-05-04,0,No rating comment.\n"  # Rejected rating 0
            "1005,999999,2020-05-05,5,Unmatched recipe review.\n",  # Unmatched recipe ID
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_importer_dry_run_all(self):
        importer = FoodComImporter(
            source_path=self.dir_path,
            component="all",
            batch_size=5,
            dry_run=True,
        )
        report = importer.run()

        self.assertEqual(report.status, "dry_run_passed")
        self.assertEqual(report.component, "all")

        # Recipe metrics
        self.assertEqual(report.recipe_metrics["accepted_recipes"], 2)
        self.assertEqual(report.recipe_metrics["rejected_recipes"], 1)

        # Interaction metrics
        self.assertEqual(report.interaction_metrics["valid_ratings"], 3)
        self.assertEqual(report.interaction_metrics["invalid_ratings"], 1)
        self.assertEqual(report.interaction_metrics["unmatched_ratings"], 1)

        # Report file written
        self.assertIsNotNone(report.report_file_path)
        self.assertTrue(Path(report.report_file_path).exists())

        with open(report.report_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["status"], "dry_run_passed")
            self.assertEqual(data["recipe_metrics"]["accepted_recipes"], 2)

    def test_importer_recipes_only(self):
        importer = FoodComImporter(
            source_path=self.dir_path,
            component="recipes",
            batch_size=5,
            dry_run=True,
        )
        report = importer.run()

        self.assertEqual(report.status, "dry_run_passed")
        self.assertEqual(report.recipe_metrics["accepted_recipes"], 2)
        self.assertEqual(report.interaction_metrics, {})

    def test_manifest_updates(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            manifest_path = Path(f.name)

        try:
            manifest = create_initial_manifest()
            save_manifest(manifest, manifest_path)

            # Record verified files
            record_verified_file(
                dataset_key="foodcom",
                file_name="RAW_recipes.csv",
                size_bytes=100000,
                sha256_checksum="abc_recipes",
                path=manifest_path,
            )
            record_verified_file(
                dataset_key="foodcom",
                file_name="RAW_interactions.csv",
                size_bytes=50000,
                sha256_checksum="def_interactions",
                path=manifest_path,
            )

            m1 = load_manifest(manifest_path)
            self.assertEqual(m1.datasets["foodcom"].import_status, STATUS_VERIFIED)
        finally:
            manifest_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
