"""Unit tests for RecipeNLG dataset ingestion pipeline using synthetic fixtures.

Note: All test datasets utilized herein are synthetic unit-test mocks created solely
for validating parser, schema, error-handling, and normalization logic. They do NOT
represent official RecipeNLG records.
"""

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from ingestion.manifest import (
    STATUS_COMPLETED,
    STATUS_DOWNLOADED,
    STATUS_NOT_DOWNLOADED,
    STATUS_VERIFIED,
    create_initial_manifest,
    load_manifest,
    record_ingestion_success,
    record_verified_file,
    save_manifest,
)


class TestRecipeNLGParser(unittest.TestCase):
    """Test JSON & Python list parsing, quantity/unit extraction, and text cleaning."""

    def test_safe_parse_list_json(self):
        # Valid JSON array
        res = safe_parse_list('["2 cups flour", "1 tsp salt", "1 cup water"]')
        self.assertEqual(res, ["2 cups flour", "1 tsp salt", "1 cup water"])

        # Empty array
        self.assertEqual(safe_parse_list("[]"), [])
        self.assertEqual(safe_parse_list(None), [])
        self.assertEqual(safe_parse_list(""), [])

    def test_safe_parse_list_python_literal(self):
        # Python literal single-quoted strings
        res = safe_parse_list("['2 cups flour', '1 tsp salt']")
        self.assertEqual(res, ["2 cups flour", "1 tsp salt"])

        # Mixed quotes and whitespace
        res = safe_parse_list("[\n  'line 1',\n  \"line 2\"\n]")
        self.assertEqual(res, ["line 1", "line 2"])

    def test_safe_parse_list_malformed_and_security(self):
        # Malformed non-list
        with self.assertRaises(RecipeNLGParseError):
            safe_parse_list("not a list")

        with self.assertRaises(RecipeNLGParseError):
            safe_parse_list("{'key': 'value'}")

        # Code execution attempts rejected
        with self.assertRaises(RecipeNLGParseError):
            safe_parse_list("__import__('os').system('dir')")

        with self.assertRaises(RecipeNLGParseError):
            safe_parse_list("[open('fake').read()]")

        # Non-string elements in list rejected
        with self.assertRaises(RecipeNLGParseError):
            safe_parse_list("[1, 2, 3]")

        with self.assertRaises(RecipeNLGParseError):
            safe_parse_list("['valid string', {'nested': 'dict'}]")

    def test_parse_ingredient_amount_and_unit(self):
        # Integer + unit
        qty, unit = parse_ingredient_amount_and_unit("2 cups all-purpose flour")
        self.assertEqual(qty, 2.0)
        self.assertEqual(unit, "cup")

        # Decimal + unit
        qty, unit = parse_ingredient_amount_and_unit("1.5 tbsp olive oil")
        self.assertEqual(qty, 1.5)
        self.assertEqual(unit, "tbsp")

        # Simple fraction + unit
        qty, unit = parse_ingredient_amount_and_unit("1/2 tsp ground cinnamon")
        self.assertEqual(qty, 0.5)
        self.assertEqual(unit, "tsp")

        # Mixed fraction + unit
        qty, unit = parse_ingredient_amount_and_unit("1 1/4 lbs chicken breast")
        self.assertEqual(qty, 1.25)
        self.assertEqual(unit, "lb")

        # No unit (just quantity)
        qty, unit = parse_ingredient_amount_and_unit("3 large eggs")
        self.assertEqual(qty, 3.0)
        self.assertIsNone(unit)

        # Unquantified text returns None, None
        qty, unit = parse_ingredient_amount_and_unit("salt and freshly ground black pepper to taste")
        self.assertIsNone(qty)
        self.assertIsNone(unit)

        # Empty input
        qty, unit = parse_ingredient_amount_and_unit("")
        self.assertIsNone(qty)
        self.assertIsNone(unit)

    def test_clean_text(self):
        self.assertEqual(clean_text("  Fresh Basil  "), "Fresh Basil")
        self.assertIsNone(clean_text(None))
        self.assertIsNone(clean_text("   \n\t  "))
        self.assertEqual(clean_text("Clean\x00Text"), "CleanText")


class TestRecipeNLGValidator(unittest.TestCase):
    """Test header verification, unified ID generation, source classification, and validation rules."""

    def test_header_validation_case_variants(self):
        # Standard lowercase headers
        valid_headers = ["id", "title", "ingredients", "directions", "link", "source", "ner"]
        ok, missing = validate_headers(valid_headers)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

        # Mixed and uppercase headers (as documented in prompt)
        mixed_headers = ["ID", "Title", "Ingredients", "DIRECTIONS", "Link", "Source", "NER"]
        ok, missing = validate_headers(mixed_headers)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

        # Missing required header ('title')
        bad_headers = ["id", "ingredients", "directions", "link", "source"]
        ok, missing = validate_headers(bad_headers)
        self.assertFalse(ok)
        self.assertIn("title", missing)

    def test_header_validation_pandas_index_and_unnamed(self):
        # Empty string as first header (standard pandas index=True)
        headers_empty_first = ["", "title", "ingredients", "directions", "link", "source", "ner"]
        ok, missing = validate_headers(headers_empty_first)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

        # 'Unnamed: 0' as first header
        headers_unnamed_first = ["Unnamed: 0", "title", "ingredients", "directions", "link", "source", "NER"]
        ok, missing = validate_headers(headers_unnamed_first)
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_header_validation_rejects_empty_or_unnamed_in_non_first_columns(self):
        # Empty header in column index 1
        headers_empty_col1 = ["id", "", "ingredients", "directions", "link", "source"]
        ok, missing = validate_headers(headers_empty_col1)
        self.assertFalse(ok)
        self.assertEqual(missing, ["invalid_empty_header_at_column_1"])

        # Empty header in non-first column with empty index 0
        headers_empty_col2 = ["", "title", "", "directions", "link", "source"]
        ok, missing = validate_headers(headers_empty_col2)
        self.assertFalse(ok)
        self.assertEqual(missing, ["invalid_empty_header_at_column_2"])

        # Unnamed in column index 2
        headers_unnamed_col2 = ["id", "title", "Unnamed: 0", "directions", "link", "source"]
        ok, missing = validate_headers(headers_unnamed_col2)
        self.assertFalse(ok)
        self.assertEqual(missing, ["invalid_unnamed_header_at_column_2"])

        # Empty header list
        ok, missing = validate_headers([])
        self.assertFalse(ok)
        self.assertEqual(missing, ["empty_header_list"])

    def test_validate_recipe_record_standard(self):
        row = {
            "id": "108294",
            "title": "Hearty Beef Stew",
            "ingredients": '["2 lbs beef chuck, cubed", "3 carrots, sliced", "2 cups beef broth"]',
            "directions": '["Brown the beef in a pot.", "Add vegetables and broth.", "Simmer for 2 hours."]',
            "link": "https://www.allrecipes.com/recipe/108294",
            "source": "Gathered",
            "ner": '["beef chuck", "carrots", "beef broth"]',
        }

        rec = validate_recipe_record(row, line_number=2)
        self.assertEqual(rec.id, "rcp_nlg_108294")
        self.assertEqual(rec.source_id, "108294")
        self.assertEqual(rec.source_dataset, "recipenlg")
        self.assertEqual(rec.title, "Hearty Beef Stew")
        self.assertEqual(rec.source_origin, "Gathered")
        self.assertEqual(rec.source_url, "https://www.allrecipes.com/recipe/108294")
        self.assertEqual(len(rec.ingredients), 3)
        self.assertEqual(len(rec.instructions), 3)
        self.assertEqual(len(rec.ner_entities), 3)
        self.assertFalse(rec.has_ner_failure)
        self.assertFalse(rec.has_missing_directions)

    def test_validate_recipe_record_id_zero(self):
        # ID zero is a valid identifier in RecipeNLG
        row = {
            "id": "0",
            "title": "Basic Toast",
            "ingredients": '["1 slice bread", "1 tbsp butter"]',
            "directions": '["Toast bread.", "Spread butter."]',
            "link": "https://recipes.com/0",
            "source": "Recipes1M",
            "ner": '["bread", "butter"]',
        }
        rec = validate_recipe_record(row, line_number=2)
        self.assertEqual(rec.id, "rcp_nlg_0")
        self.assertEqual(rec.source_id, "0")
        self.assertEqual(rec.source_origin, "Recipes1M")

    def test_validate_recipe_record_duplicate_detection(self):
        seen = {"108294"}
        row = {
            "id": "108294",
            "title": "Duplicate Recipe",
            "ingredients": '["water"]',
            "directions": '["boil"]',
            "link": "",
            "source": "Gathered",
        }
        with self.assertRaises(DuplicateRecipeIDError):
            validate_recipe_record(row, line_number=5, seen_ids=seen)

    def test_validate_recipe_record_edge_cases(self):
        base_row = {
            "id": "500",
            "title": "Sample Recipe",
            "ingredients": '["flour", "water"]',
            "directions": '["mix"]',
            "link": "",
            "source": "Gathered",
        }

        # Empty title rejected
        bad_title_row = dict(base_row, title="")
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(bad_title_row, line_number=2)

        # Negative ID rejected
        neg_id_row = dict(base_row, id="-1")
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(neg_id_row, line_number=3)

        # Non-numeric ID rejected
        str_id_row = dict(base_row, id="abc")
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(str_id_row, line_number=4)

        # Empty ingredients rejected
        no_ing_row = dict(base_row, ingredients="[]")
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(no_ing_row, line_number=5)

        # Empty directions accepted with has_missing_directions flag
        no_dir_row = dict(base_row, directions="[]")
        rec = validate_recipe_record(no_dir_row, line_number=6)
        self.assertTrue(rec.has_missing_directions)
        self.assertEqual(rec.instructions, [])

        # Malformed NER tolerated with has_ner_failure flag
        bad_ner_row = dict(base_row, ner="[invalid json")
        rec = validate_recipe_record(bad_ner_row, line_number=7)
        self.assertTrue(rec.has_ner_failure)
        self.assertIsNone(rec.ner_entities)

        # Title truncation to 512 chars
        long_title_row = dict(base_row, title="X" * 600)
        rec = validate_recipe_record(long_title_row, line_number=8)
        self.assertEqual(len(rec.title), 512)

    def test_validate_recipe_record_source_origin_constraint_compliance(self):
        """Verify source_origin maps to 'Gathered', 'Recipes1M', or None (SQL NULL) to satisfy Migration 005."""
        base_row = {
            "id": "600",
            "title": "Origin Recipe",
            "ingredients": '["sugar"]',
            "directions": '["stir"]',
            "link": "",
        }

        # Gathered variants
        for val in ("Gathered", "gathered", "1"):
            rec = validate_recipe_record(dict(base_row, source=val), line_number=2)
            self.assertEqual(rec.source_origin, "Gathered")

        # Recipes1M variants
        for val in ("Recipes1M", "recipes1m", "recipe1m", "0"):
            rec = validate_recipe_record(dict(base_row, source=val), line_number=3)
            self.assertEqual(rec.source_origin, "Recipes1M")

        # Unknown / Unrecognized / Missing / Empty values must evaluate to None (NULL)
        # to strictly satisfy Migration 005 check constraint:
        # CHECK (source_origin IS NULL OR source_origin IN ('Gathered', 'Recipes1M'))
        for val in ("allrecipes.com", "custom_crawler", "2", "", None):
            rec = validate_recipe_record(dict(base_row, source=val), line_number=4)
            self.assertIsNone(rec.source_origin)

    def test_validate_recipe_record_empty_first_column_pandas_index(self):
        # Empty first column key '' with integer ID 0
        row_id_0 = {
            "": "0",
            "title": "No-Bake Cookies",
            "ingredients": '["oats", "peanut butter"]',
            "directions": '["mix", "chill"]',
            "link": "https://recipes.com/0",
            "source": "Gathered",
            "ner": '["oats", "peanut butter"]',
        }
        rec0 = validate_recipe_record(row_id_0, line_number=2)
        self.assertEqual(rec0.id, "rcp_nlg_0")
        self.assertEqual(rec0.source_id, "0")
        self.assertEqual(rec0.title, "No-Bake Cookies")

        # Large integer ID in empty first column
        row_large = {
            "": "2231141",
            "title": "Grand Final Recipe",
            "ingredients": '["flour", "water"]',
            "directions": '["bake"]',
            "link": "",
            "source": "Recipes1M",
        }
        rec_large = validate_recipe_record(row_large, line_number=2231143)
        self.assertEqual(rec_large.id, "rcp_nlg_2231141")
        self.assertEqual(rec_large.source_id, "2231141")

    def test_validate_recipe_record_unnamed_zero_header(self):
        row = {
            "Unnamed: 0": "42",
            "title": "Hitchhiker Stew",
            "ingredients": '["tea", "biscuits"]',
            "directions": '["dunk"]',
            "link": "",
            "source": "Gathered",
        }
        rec = validate_recipe_record(row, line_number=5)
        self.assertEqual(rec.id, "rcp_nlg_42")
        self.assertEqual(rec.source_id, "42")

    def test_validate_recipe_record_empty_header_validation_errors(self):
        # Non-integer value in empty first column
        bad_val_row = {
            "": "not_a_number",
            "title": "Bad ID Recipe",
            "ingredients": '["flour"]',
            "directions": '["bake"]',
            "link": "",
            "source": "Gathered",
        }
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(bad_val_row, line_number=10)

        # Negative ID in empty first column
        neg_val_row = {
            "": "-10",
            "title": "Neg ID Recipe",
            "ingredients": '["flour"]',
            "directions": '["bake"]',
            "link": "",
            "source": "Gathered",
        }
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(neg_val_row, line_number=11)

        # Empty string ID in empty first column
        empty_val_row = {
            "": "",
            "title": "Empty ID Recipe",
            "ingredients": '["flour"]',
            "directions": '["bake"]',
            "link": "",
            "source": "Gathered",
        }
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(empty_val_row, line_number=12)

        # Empty key in non-first column without an 'id' column
        non_first_empty_key = {
            "title": "Misplaced Empty Key Recipe",
            "": "100",
            "ingredients": '["flour"]',
            "directions": '["bake"]',
            "link": "",
            "source": "Gathered",
        }
        with self.assertRaises(RecipeNLGValidationError):
            validate_recipe_record(non_first_empty_key, line_number=13)

        # Duplicate ID with empty header column
        seen_ids = {"0", "1"}
        dup_row = {
            "": "0",
            "title": "Duplicate Zero",
            "ingredients": '["flour"]',
            "directions": '["bake"]',
            "link": "",
            "source": "Gathered",
        }
        with self.assertRaises(DuplicateRecipeIDError):
            validate_recipe_record(dup_row, line_number=14, seen_ids=seen_ids)


class TestRecipeNLGSourceAndZipHandling(unittest.TestCase):
    """Test streaming file reader for uncompressed directories, direct CSV, and ZIP archives."""

    def test_direct_csv_source(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
            f.write("id,title,ingredients,directions,link,source,ner\n")
            f.write('0,"Toast","[\'bread\']","[\'toast\']","","Gathered","[\'bread\']"\n')
            csv_path = Path(f.name)

        try:
            source = RecipeNLGSource(csv_path)
            self.assertTrue(source.has_file("full_dataset.csv"))
            headers = source.inspect_headers()
            self.assertEqual(headers, ["id", "title", "ingredients", "directions", "link", "source", "ner"])

            rows = list(source.open_csv_stream())
            self.assertEqual(len(rows), 1)
            line_num, row = rows[0]
            self.assertEqual(line_num, 2)
            self.assertEqual(row["title"], "Toast")
        finally:
            csv_path.unlink(missing_ok=True)

    def test_zip_source_without_extraction(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "recipenlg.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr(
                    "recipenlg/full_dataset.csv",
                    "id,title,ingredients,directions,link,source,ner\n"
                    '101,"Apple Pie","[\'apples\', \'flour\']","[\'bake\']","","Recipes1M","[\'apples\']"\n'
                )

            source = RecipeNLGSource(zip_path)
            self.assertTrue(source.is_zip)
            self.assertTrue(source.has_file("full_dataset.csv"))
            headers = source.inspect_headers()
            self.assertEqual(headers[0], "id")

            rows = list(source.open_csv_stream())
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][1]["title"], "Apple Pie")

    def test_zip_source_with_recipenlg_dataset_csv_alias(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            zip_path = Path(tmp_dir) / "archive.zip"
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr(
                    "RecipeNLG_dataset.csv",
                    ',title,ingredients,directions,link,source,NER\n'
                    '0,"No-Bake Nut Cookies","[\'1 c. firmly packed brown sugar\']","[\'In heavy saucepan, combine brown sugar...\']","https://recipes.com/0","Gathered","[\'brown sugar\']"\n'
                )

            source = RecipeNLGSource(zip_path)
            self.assertTrue(source.is_zip)
            # Both canonical 'full_dataset.csv' and actual member 'RecipeNLG_dataset.csv' resolve
            self.assertTrue(source.has_file("full_dataset.csv"))
            self.assertTrue(source.has_file("RecipeNLG_dataset.csv"))

            headers = source.inspect_headers("full_dataset.csv")
            self.assertEqual(headers[0], "")
            self.assertEqual(headers[1], "title")

            rows = list(source.open_csv_stream("full_dataset.csv"))
            self.assertEqual(len(rows), 1)
            line_num, row = rows[0]
            self.assertEqual(line_num, 2)
            self.assertEqual(row[""], "0")
            self.assertEqual(row["title"], "No-Bake Nut Cookies")

    def test_missing_file_raises_error(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = RecipeNLGSource(Path(tmp_dir))
            with self.assertRaises(FileNotFoundError):
                list(source.open_csv_stream("full_dataset.csv"))


class TestRecipeNLGLoaderAndCanonicalMatching(unittest.TestCase):
    """Test canonical ingredient linking, ambiguity detection, and batch queries."""

    def test_canonical_matching_logic(self):
        canon_map = {
            "all-purpose flour": 1,
            "flour": 1,
            "white sugar": 2,
            "sugar": 2,
            "butter": 3,
            "brown sugar": 4,
        }

        # 1. Exact direct match
        id_match, ambig = RecipeNLGLoader.match_canonical_ingredient("flour", None, canon_map)
        self.assertEqual(id_match, 1)
        self.assertFalse(ambig)

        # 2. NER single unambiguous match
        id_match, ambig = RecipeNLGLoader.match_canonical_ingredient(
            raw_text="2 cups unbleached all-purpose flour",
            ner_entities=["all-purpose flour"],
            canon_map=canon_map,
        )
        self.assertEqual(id_match, 1)
        self.assertFalse(ambig)

        # 3. Ambiguous match: multiple distinct canonical IDs detected in one raw line
        # e.g., line mentions both butter and sugar
        id_match, ambig = RecipeNLGLoader.match_canonical_ingredient(
            raw_text="mixture of melted butter and white sugar",
            ner_entities=["butter", "white sugar"],
            canon_map=canon_map,
        )
        self.assertIsNone(id_match)
        self.assertTrue(ambig)

        # 4. Unmatched ingredient
        id_match, ambig = RecipeNLGLoader.match_canonical_ingredient(
            raw_text="1 tsp exotic dragonfruit powder",
            ner_entities=["dragonfruit powder"],
            canon_map=canon_map,
        )
        self.assertIsNone(id_match)
        self.assertFalse(ambig)

    def test_loader_batch_queries(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        loader = RecipeNLGLoader(mock_conn)

        recipes = [
            ValidatedRecipeNLG(
                id="rcp_nlg_101",
                source_id="101",
                source_dataset="recipenlg",
                title="Rustic Sourdough Bread",
                source_origin="Gathered",
                source_url="https://recipes.com/101",
                ingredients=["3 cups flour", "1 tsp salt", "1 cup warm water"],
                instructions=["Mix flour and water.", "Knead dough.", "Bake at 450F."],
                ner_entities=["flour", "salt"],
                line_number=2,
            )
        ]

        canon_map = {"flour": 10, "salt": 20}
        counts = loader.load_recipes_batch(recipes, canonical_map=canon_map, has_source_origin=True)

        self.assertEqual(counts["recipes"], 1)
        self.assertEqual(counts["recipe_ingredients"], 3)
        self.assertEqual(counts["recipe_instructions"], 3)
        self.assertEqual(counts["canonical_links"], 2)
        self.assertEqual(counts["ambiguous_ingredients"], 0)

        # Verify child row cleanup executed before re-insertion
        execute_sqls = [call[0][0] for call in mock_cur.execute.call_args_list]
        self.assertTrue(any("DELETE FROM recipe_catalog.recipe_ingredients" in sql for sql in execute_sqls))
        self.assertTrue(any("DELETE FROM recipe_catalog.recipe_instructions" in sql for sql in execute_sqls))

        # Verify executemany executed for recipes, ingredients, instructions
        self.assertTrue(mock_cur.executemany.called)


class TestRecipeNLGImporterDryRunAndManifest(unittest.TestCase):
    """Test full importer dry-run simulation, audit reporting, and manifest updates."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Synthetic full_dataset.csv containing:
        # Line 2: Valid Gathered recipe
        # Line 3: Valid Recipes1M recipe with ID 0
        # Line 4: Recipe with missing directions (tolerated)
        # Line 5: Recipe with malformed NER (tolerated)
        # Line 6: Duplicate recipe ID (rejected)
        # Line 7: Empty title (rejected)
        # Line 8: Empty ingredients (rejected)
        (self.dir_path / "full_dataset.csv").write_text(
            'id,title,ingredients,directions,link,source,ner\n'
            '1001,"Pancake Stack","[\'1 cup flour\', \'1 egg\', \'1 cup milk\']","[\'Whisk ingredients\', \'Cook on griddle\']","https://link1.com","Gathered","[\'flour\', \'egg\', \'milk\']"\n'
            '0,"Morning Omelette","[\'2 eggs\', \'1 tbsp butter\', \'salt\']","[\'Beat eggs\', \'Melt butter\', \'Fold omelette\']","https://link0.com","Recipes1M","[\'eggs\', \'butter\']"\n'
            '1002,"Quick Lemon Water","[\'1 lemon, juiced\', \'2 cups water\']","[]","https://link2.com","Gathered","[\'lemon\', \'water\']"\n'
            '1003,"Garlic Toast","[\'2 slices bread\', \'1 clove garlic\']","[\'Rub garlic on bread\', \'Toast\']","https://link3.com","Gathered","[invalid_ner"\n'
            '1001,"Duplicate Pancake Stack","[\'flour\']","[\'cook\']","","Gathered","[\'flour\']"\n'
            '1004,"","[\'flour\']","[\'cook\']","","Gathered","[\'flour\']"\n'
            '1005,"Empty Ingredients Recipe","[]","[\'step\']","","Gathered","[]"\n',
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_importer_dry_run_execution(self):
        importer = RecipeNLGImporter(
            source_path=self.dir_path,
            batch_size=5,
            dry_run=True,
        )
        report = importer.run()

        self.assertEqual(report.status, "dry_run_passed")
        self.assertEqual(report.metrics["total_source_rows"], 7)
        self.assertEqual(report.metrics["accepted_recipes"], 4)
        self.assertEqual(report.metrics["rejected_rows"], 3)
        self.assertEqual(report.metrics["duplicate_source_ids"], 1)
        self.assertEqual(report.metrics["empty_titles"], 1)
        self.assertEqual(report.metrics["missing_or_malformed_ingredients"], 1)
        self.assertEqual(report.metrics["missing_directions_recipes"], 1)
        self.assertEqual(report.metrics["ner_failures"], 1)

        # Check sample rejections captured
        self.assertTrue(len(report.sample_rejections) >= 3)

        # Check JSON audit report file
        self.assertIsNotNone(report.report_file_path)
        self.assertTrue(Path(report.report_file_path).exists())

        with open(report.report_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["status"], "dry_run_passed")
            self.assertEqual(data["metrics"]["accepted_recipes"], 4)

    def test_manifest_success_update(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            manifest_path = Path(f.name)

        try:
            manifest = create_initial_manifest()
            save_manifest(manifest, manifest_path)

            # Record verified file
            record_verified_file(
                dataset_key="recipenlg",
                file_name="full_dataset.csv",
                size_bytes=2147483648,
                sha256_checksum="abc_recipenlg",
                path=manifest_path,
            )
            m1 = load_manifest(manifest_path)
            self.assertEqual(m1.datasets["recipenlg"].import_status, STATUS_VERIFIED)

            # Record ingestion success
            record_ingestion_success(
                dataset_key="recipenlg",
                imported_counts={"recipes": 2231142, "recipe_ingredients": 15000000},
                path=manifest_path,
            )
            m2 = load_manifest(manifest_path)
            self.assertEqual(m2.datasets["recipenlg"].import_status, STATUS_COMPLETED)
            self.assertEqual(m2.datasets["recipenlg"].imported_row_counts["recipes"], 2231142)
        finally:
            manifest_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

