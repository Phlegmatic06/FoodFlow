"""Unit tests for the ingestion command-line interface."""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingestion.cli import build_parser, main
from ingestion.config import DATASET_REGISTRY


class TestCLI(unittest.TestCase):

    def setUp(self):
        self.parser = build_parser()

    def test_parser_subcommands(self):
        # Assert subcommands exist
        for cmd in ["doctor", "status"]:
            args = self.parser.parse_args([cmd])
            self.assertEqual(args.command, cmd)

        args = self.parser.parse_args(["inspect", "--dataset", "usda"])
        self.assertEqual(args.command, "inspect")

        args = self.parser.parse_args(["verify", "--dataset", "foodcom"])
        self.assertEqual(args.command, "verify")

        args = self.parser.parse_args(["ingest-usda", "-t", "foundation", "-s", "fake.zip"])
        self.assertEqual(args.command, "ingest-usda")

        args = self.parser.parse_args(["ingest-foodcom", "-s", "fake_dir", "-c", "recipes", "--dry-run"])
        self.assertEqual(args.command, "ingest-foodcom")
        self.assertEqual(args.component, "recipes")
        self.assertTrue(args.dry_run)

        args = self.parser.parse_args(["ingest-recipenlg", "-s", "fake_dataset.csv", "--dry-run", "--limit", "50", "--force"])
        self.assertEqual(args.command, "ingest-recipenlg")
        self.assertTrue(args.dry_run)
        self.assertEqual(args.limit, 50)
        self.assertTrue(args.force)

        args = self.parser.parse_args(["sample", "-d", "foodcom", "-s", "fake_dir", "--limit", "100", "--seed", "123", "--dry-run"])
        self.assertEqual(args.command, "sample")
        self.assertEqual(args.dataset, "foodcom")
        self.assertEqual(args.limit, 100)
        self.assertEqual(args.seed, 123)
        self.assertTrue(args.dry_run)

        args = self.parser.parse_args(["sample", "-d", "recipenlg", "-s", "fake.csv"])
        self.assertEqual(args.command, "sample")
        self.assertEqual(args.dataset, "recipenlg")
        self.assertEqual(args.limit, 25000)
        self.assertEqual(args.seed, 42)
        self.assertFalse(args.dry_run)

    def test_doctor_command_execution(self):
        # Test doctor command stdout capture
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            exit_code = main(["doctor"])
        output = captured.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("NutriPod Ingestion Environment Doctor", output)
        self.assertIn("Python Version:", output)
        self.assertIn("Data & Report Directories", output)

    def test_inspect_missing_dataset_returns_exit_code_1(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            exit_code = main(["inspect", "--dataset", "foodcom"])
        output = captured.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("Dataset Inspection: Food.com Recipes and Interactions", output)
        self.assertIn("Action Required: Missing Files", output)
        self.assertIn("Download Instructions:", output)

    def test_inspect_with_synthetic_present_file(self):
        # Create a synthetic CSV in a temporary directory and test inspection
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            sample_file = tmp_path / "RAW_recipes.csv"
            with open(sample_file, "w", encoding="utf-8") as f:
                f.write("name,id,minutes,contributor_id,submitted,tags,nutrition,n_steps,steps,description,ingredients,n_ingredients\n")
                f.write("Banana Bread,101,45,42,'2020-01-01','[easy]','[200, 5, 10, 10, 5, 2, 30]',3,'[bake]','tasty','[banana]',1\n")

            # Temporarily point registry raw_directory to tmp_path
            orig_dir = DATASET_REGISTRY["foodcom"].raw_directory
            try:
                object.__setattr__(DATASET_REGISTRY["foodcom"], "raw_directory", tmp_path)
                captured = io.StringIO()
                with patch("sys.stdout", captured):
                    # We have RAW_recipes.csv present, RAW_interactions.csv missing
                    exit_code = main(["inspect", "--dataset", "foodcom", "--count-rows"])
                output = captured.getvalue()
                self.assertIn("File: RAW_recipes.csv", output)
                self.assertIn("[PRESENT]", output)
                self.assertIn("1 data rows", output)
                self.assertIn("File: RAW_interactions.csv", output)
                self.assertIn("[MISSING]", output)
            finally:
                object.__setattr__(DATASET_REGISTRY["foodcom"], "raw_directory", orig_dir)

    def test_status_command_execution(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            exit_code = main(["status"])
        output = captured.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("NutriPod Dataset Ingestion Framework Status", output)
        self.assertIn("usda", output)
        self.assertIn("foodcom", output)
        self.assertIn("recipenlg", output)

    def test_verify_command_execution(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            exit_code = main(["verify"])
        output = captured.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Verification Summary", output)
        self.assertIn("Total Expected Files : 7", output)


if __name__ == "__main__":
    unittest.main()

