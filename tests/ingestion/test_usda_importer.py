"""Unit tests for USDA FoodData Central ingestion pipeline using synthetic fixtures.

Note: All test datasets utilized herein are synthetic unit-test mocks created solely
for validating parser, schema, and error-handling logic. They do NOT represent
official USDA FoodData Central records.
"""

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ingestion.datasets.usda.importer import USDAImporter
from ingestion.datasets.usda.loader import USDALoader
from ingestion.datasets.usda.parser import (
    USDAParseError,
    USDASource,
    clean_text,
    parse_date,
    parse_float,
    parse_int,
)
from ingestion.datasets.usda.validator import (
    USDAValidationError,
    validate_food_nutrient_record,
    validate_food_portion_record,
    validate_food_record,
    validate_headers,
    validate_nutrient_record,
)
from ingestion.manifest import (
    STATUS_COMPLETED,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_NOT_DOWNLOADED,
    STATUS_PARTIALLY_IMPORTED,
    create_initial_manifest,
    load_manifest,
    record_collection_failure,
    record_collection_file,
    record_collection_success,
    save_manifest,
)


class TestUSDAParserAndCoercion(unittest.TestCase):

    def test_clean_text(self):
        self.assertIsNone(clean_text(None))
        self.assertIsNone(clean_text(""))
        self.assertIsNone(clean_text("   \t\n  "))
        self.assertEqual(clean_text("  Chicken Breast  "), "Chicken Breast")

    def test_parse_int(self):
        self.assertIsNone(parse_int(None))
        self.assertIsNone(parse_int(""))
        self.assertEqual(parse_int("100"), 100)
        self.assertEqual(parse_int("100.0"), 100)
        with self.assertRaises(ValueError):
            parse_int("not_a_number")

    def test_parse_float(self):
        self.assertIsNone(parse_float(None))
        self.assertIsNone(parse_float(""))
        self.assertEqual(parse_float("23.50"), 23.50)
        with self.assertRaises(ValueError):
            parse_float("invalid_float")

    def test_parse_date(self):
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date(""))
        self.assertEqual(parse_date("2024-10-31"), "2024-10-31")
        self.assertEqual(parse_date("2024-10-31 00:00:00"), "2024-10-31")
        with self.assertRaises(ValueError):
            parse_date("31/10/2024")


class TestUSDAHeaderAndRecordValidation(unittest.TestCase):

    def test_header_validation(self):
        valid_food_headers = ["fdc_id", "data_type", "description", "food_category_id", "publication_date"]
        ok, missing = validate_headers("food.csv", valid_food_headers)
        self.assertTrue(ok)
        self.assertEqual(len(missing), 0)

        # Missing required description
        invalid_headers = ["fdc_id", "data_type"]
        ok, missing = validate_headers("food.csv", invalid_headers)
        self.assertFalse(ok)
        self.assertIn("description", missing)

    def test_validate_food_record(self):
        valid_row = {
            "fdc_id": "1001",
            "data_type": "foundation_food",
            "description": "Butter, without salt",
            "food_category_id": "1",
            "publication_date": "2020-04-01",
        }
        res = validate_food_record(valid_row, line_number=2, default_data_type="foundation_food")
        self.assertEqual(res.fdc_id, 1001)
        self.assertEqual(res.data_type, "foundation_food")
        self.assertEqual(res.description, "Butter, without salt")
        self.assertEqual(res.food_category_id, 1)
        self.assertEqual(res.publication_date, "2020-04-01")

        # Invalid FDC ID
        invalid_id_row = dict(valid_row, fdc_id="invalid")
        with self.assertRaises(USDAValidationError):
            validate_food_record(invalid_id_row, line_number=3, default_data_type="foundation_food")

        # Missing description
        no_desc_row = dict(valid_row, description="")
        with self.assertRaises(USDAValidationError):
            validate_food_record(no_desc_row, line_number=4, default_data_type="foundation_food")

    def test_validate_nutrient_record(self):
        valid_row = {
            "id": "1003",
            "name": "Protein",
            "unit_name": "G",
            "nutrient_nbr": "203",
            "rank": "600.0",
        }
        res = validate_nutrient_record(valid_row, line_number=2)
        self.assertEqual(res.id, 1003)
        self.assertEqual(res.name, "Protein")
        self.assertEqual(res.unit_name, "G")
        self.assertEqual(res.nutrient_nbr, "203")
        self.assertEqual(res.rank, 600.0)

        # Missing unit_name
        invalid_row = dict(valid_row, unit_name="")
        with self.assertRaises(USDAValidationError):
            validate_nutrient_record(invalid_row, line_number=3)

    def test_validate_food_nutrient_record(self):
        known_foods = {1001, 1002}
        known_nutrients = {1003, 1008}

        valid_row = {
            "id": "50001",
            "fdc_id": "1001",
            "nutrient_id": "1003",
            "amount": "0.85",
            "data_points": "5",
            "derivation_id": "1",
        }
        res = validate_food_nutrient_record(valid_row, line_number=2, known_foods=known_foods, known_nutrients=known_nutrients)
        self.assertEqual(res.id, 50001)
        self.assertEqual(res.fdc_id, 1001)
        self.assertEqual(res.nutrient_id, 1003)
        self.assertEqual(res.amount, 0.85)

        # NULL amount should be preserved as None (never replaced with 0.0)
        null_amount_row = dict(valid_row, amount="")
        res_null = validate_food_nutrient_record(null_amount_row, line_number=3, known_foods=known_foods, known_nutrients=known_nutrients)
        self.assertIsNone(res_null.amount)

        # Foreign key violation: unknown food
        unknown_food_row = dict(valid_row, fdc_id="9999")
        with self.assertRaises(USDAValidationError) as ctx:
            validate_food_nutrient_record(unknown_food_row, line_number=4, known_foods=known_foods, known_nutrients=known_nutrients)
        self.assertIn("Foreign key violation", str(ctx.exception))

        # Foreign key violation: unknown nutrient
        unknown_nut_row = dict(valid_row, nutrient_id="9999")
        with self.assertRaises(USDAValidationError) as ctx:
            validate_food_nutrient_record(unknown_nut_row, line_number=5, known_foods=known_foods, known_nutrients=known_nutrients)
        self.assertIn("Foreign key violation", str(ctx.exception))

    def test_validate_food_portion_record(self):
        known_foods = {1001}
        valid_row = {
            "id": "7001",
            "fdc_id": "1001",
            "seq_num": "1",
            "amount": "1.0",
            "measure_unit_id": "10",
            "portion_description": "1 tbsp",
            "modifier": "melted",
            "gram_weight": "14.2",
        }
        res = validate_food_portion_record(valid_row, line_number=2, known_foods=known_foods)
        self.assertEqual(res.id, 7001)
        self.assertEqual(res.fdc_id, 1001)
        self.assertEqual(res.gram_weight, 14.2)

        # Missing gram_weight (schema requires NOT NULL)
        missing_gw_row = dict(valid_row, gram_weight="")
        with self.assertRaises(USDAValidationError):
            validate_food_portion_record(missing_gw_row, line_number=3, known_foods=known_foods)


class TestUSDASourceAndZipHandling(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_directory_source_discovery(self):
        # Create synthetic CSVs in directory
        (self.dir_path / "food.csv").write_text("fdc_id,description\n1001,Milk\n", encoding="utf-8")
        (self.dir_path / "nutrient.csv").write_text("id,name,unit_name\n1003,Protein,G\n", encoding="utf-8")
        (self.dir_path / "food_nutrient.csv").write_text("id,fdc_id,nutrient_id,amount\n1,1001,1003,3.4\n", encoding="utf-8")

        source = USDASource(self.dir_path)
        self.assertTrue(source.has_file("food.csv"))
        self.assertTrue(source.has_file("nutrient.csv"))
        self.assertTrue(source.has_file("food_nutrient.csv"))
        self.assertFalse(source.has_file("food_portion.csv"))

        rows = list(source.open_csv_stream("food.csv"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["fdc_id"], "1001")

    def test_zip_source_without_extraction(self):
        zip_path = self.dir_path / "synthetic_usda.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            # Nested inside an archive subdirectory
            z.writestr("subfolder/food.csv", "fdc_id,description,data_type\n2001,Oats,foundation_food\n")
            z.writestr("subfolder/nutrient.csv", "id,name,unit_name\n1008,Energy,KCAL\n")
            z.writestr("subfolder/food_nutrient.csv", "id,fdc_id,nutrient_id,amount\n2,2001,1008,389.0\n")

        source = USDASource(zip_path)
        self.assertTrue(source.is_zip)
        self.assertTrue(source.has_file("food.csv"))
        self.assertTrue(source.has_file("nutrient.csv"))

        headers = source.inspect_headers("food.csv")
        self.assertEqual(headers, ["fdc_id", "description", "data_type"])

        rows = list(source.open_csv_stream("food.csv"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["description"], "Oats")


class TestUSDALoader(unittest.TestCase):

    def test_loader_idempotent_queries(self):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = []

        loader = USDALoader(mock_conn)

        # Test load foods
        foods = [
            validate_food_record({"fdc_id": "101", "description": "Apple"}, line_number=2, default_data_type="foundation_food"),
            validate_food_record({"fdc_id": "102", "description": "Orange"}, line_number=3, default_data_type="foundation_food"),
        ]
        loaded_count = loader.load_foods(foods)
        self.assertEqual(loaded_count, 2)
        mock_cur.executemany.assert_called()
        call_sql = mock_cur.executemany.call_args[0][0]
        self.assertIn("ON CONFLICT (fdc_id) DO UPDATE", call_sql)

        # Test load nutrients
        nutrients = [
            validate_nutrient_record({"id": "1003", "name": "Protein", "unit_name": "G"}, line_number=2)
        ]
        loader.load_nutrients(nutrients)
        nut_sql = mock_cur.executemany.call_args[0][0]
        self.assertIn("ON CONFLICT (id) DO NOTHING", nut_sql)


class TestUSDAImporterDryRunAndManifest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

        # Write synthetic USDA directory
        (self.dir_path / "food.csv").write_text(
            "fdc_id,description,data_type,food_category_id,publication_date\n"
            "3001,Synthetic Whole Wheat Flour,foundation_food,20,2024-10-31\n"
            "3002,Synthetic Brown Rice,foundation_food,20,2024-10-31\n"
            "invalid_id,Bad Food,foundation_food,,\n",  # 1 malformed row
            encoding="utf-8",
        )
        (self.dir_path / "nutrient.csv").write_text(
            "id,name,unit_name,nutrient_nbr,rank\n"
            "1003,Protein,G,203,600.0\n"
            "1008,Energy,KCAL,208,300.0\n",
            encoding="utf-8",
        )
        (self.dir_path / "food_nutrient.csv").write_text(
            "id,fdc_id,nutrient_id,amount,data_points,derivation_id\n"
            "1,3001,1003,13.2,3,1\n"
            "2,3001,1008,340.0,3,1\n"
            "3,3002,1003,7.5,2,1\n"
            "4,9999,1003,10.0,1,1\n",  # Unknown food FK violation
            encoding="utf-8",
        )
        (self.dir_path / "food_portion.csv").write_text(
            "id,fdc_id,seq_num,amount,measure_unit_id,portion_description,modifier,gram_weight\n"
            "1,3001,1,1.0,1,1 cup,,120.0\n"
            "2,3001,2,1.0,1,1 tbsp,,,\n",  # Missing mandatory gram weight
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_importer_dry_run_execution(self):
        importer = USDAImporter(
            source_path=self.dir_path,
            collection_type="foundation",
            batch_size=10,
            dry_run=True,
        )
        report = importer.run()

        self.assertEqual(report.status, "dry_run_passed")
        self.assertEqual(report.imported_counts["usda_foods"], 2)
        self.assertEqual(report.rejected_counts["food.csv"], 1)

        self.assertEqual(report.imported_counts["usda_nutrients"], 2)
        self.assertEqual(report.rejected_counts["nutrient.csv"], 0)

        # 3 accepted food nutrients, 1 rejected (foreign key violation 9999)
        self.assertEqual(report.imported_counts["usda_food_nutrients"], 3)
        self.assertEqual(report.rejected_counts["food_nutrient.csv"], 1)

        # 1 accepted food portion, 1 rejected (missing gram_weight)
        self.assertEqual(report.imported_counts["usda_food_portions"], 1)
        self.assertEqual(report.rejected_counts["food_portion.csv"], 1)

        self.assertTrue(len(report.sample_rejections) > 0)

    def test_manifest_collection_transitions(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            manifest_path = Path(f.name)

        try:
            manifest = create_initial_manifest()
            save_manifest(manifest, manifest_path)

            # Record foundation file
            record_collection_file(
                dataset_key="usda",
                collection_id="foundation",
                file_name="food.csv",
                size_bytes=10000,
                sha256_checksum="abc_foundation",
                path=manifest_path,
            )
            m1 = load_manifest(manifest_path)
            self.assertEqual(
                m1.datasets["usda"].collections["foundation"]["import_status"],
                STATUS_DOWNLOADED,
            )

            # Record foundation success -> parent dataset transitions to partially_imported
            record_collection_success(
                dataset_key="usda",
                collection_id="foundation",
                imported_counts={"usda_foods": 8000, "usda_food_nutrients": 50000},
                path=manifest_path,
            )
            m2 = load_manifest(manifest_path)
            self.assertEqual(m2.datasets["usda"].import_status, STATUS_PARTIALLY_IMPORTED)
            self.assertEqual(
                m2.datasets["usda"].collections["foundation"]["import_status"],
                STATUS_COMPLETED,
            )

            # Record sr_legacy success -> parent dataset transitions to completed
            record_collection_success(
                dataset_key="usda",
                collection_id="sr_legacy",
                imported_counts={"usda_foods": 7793, "usda_food_nutrients": 45000},
                path=manifest_path,
            )
            m3 = load_manifest(manifest_path)
            self.assertEqual(m3.datasets["usda"].import_status, STATUS_COMPLETED)
            self.assertEqual(
                m3.datasets["usda"].collections["sr_legacy"]["import_status"],
                STATUS_COMPLETED,
            )
            self.assertEqual(m3.datasets["usda"].imported_row_counts["usda_foods"], 15793)

            # Record failure
            record_collection_failure(
                dataset_key="usda",
                collection_id="foundation",
                step="insert_nutrients",
                error_message="Simulated DB error",
                path=manifest_path,
            )
            m4 = load_manifest(manifest_path)
            self.assertEqual(m4.datasets["usda"].import_status, STATUS_FAILED)
            self.assertEqual(
                m4.datasets["usda"].collections["foundation"]["import_status"],
                STATUS_FAILED,
            )
        finally:
            if manifest_path.exists():
                manifest_path.unlink()


if __name__ == "__main__":
    unittest.main()

