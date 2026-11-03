"""Unit tests for dataset manifest schema, serialization, and state tracking."""

import tempfile
import unittest
from pathlib import Path

from ingestion.manifest import (
    STATUS_COMPLETED,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_NOT_DOWNLOADED,
    STATUS_VERIFIED,
    create_initial_manifest,
    load_manifest,
    record_ingestion_failure,
    record_ingestion_success,
    record_verified_file,
    save_manifest,
)


class TestManifest(unittest.TestCase):

    def test_initial_manifest_integrity(self):
        manifest = create_initial_manifest()
        self.assertEqual(manifest.version, "1.0.0")
        self.assertEqual(len(manifest.datasets), 3)

        for key, entry in manifest.datasets.items():
            self.assertEqual(entry.import_status, STATUS_NOT_DOWNLOADED)
            self.assertIsNone(entry.download_date)
            self.assertIsNone(entry.last_successful_ingestion)
            self.assertIsNone(entry.failure_record)
            self.assertEqual(len(entry.files), 0)
            self.assertEqual(len(entry.imported_row_counts), 0)
            self.assertTrue(len(entry.expected_files) > 0)
            self.assertTrue(len(entry.official_source_url) > 0)

    def test_manifest_serialization_roundtrip(self):
        manifest = create_initial_manifest()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            save_manifest(manifest, temp_path)
            loaded = load_manifest(temp_path)
            self.assertEqual(loaded.version, manifest.version)
            self.assertEqual(set(loaded.datasets.keys()), set(manifest.datasets.keys()))
            self.assertEqual(
                loaded.datasets["usda"].official_source_url,
                manifest.datasets["usda"].official_source_url,
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_record_verified_file_and_status_transitions(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            manifest = create_initial_manifest()
            save_manifest(manifest, temp_path)

            # Record 1 of 4 files for USDA -> should be STATUS_DOWNLOADED
            record_verified_file(
                dataset_key="usda",
                file_name="food.csv",
                size_bytes=10240,
                sha256_checksum="abc123hash",
                path=temp_path,
            )
            loaded = load_manifest(temp_path)
            self.assertEqual(loaded.datasets["usda"].import_status, STATUS_DOWNLOADED)
            self.assertIn("food.csv", loaded.datasets["usda"].files)
            self.assertEqual(loaded.datasets["usda"].files["food.csv"].size_bytes, 10240)

            # Record remaining 3 files -> should transition to STATUS_VERIFIED
            for fn in ["nutrient.csv", "food_nutrient.csv", "food_portion.csv"]:
                record_verified_file(
                    dataset_key="usda",
                    file_name=fn,
                    size_bytes=5000,
                    sha256_checksum=f"hash_{fn}",
                    path=temp_path,
                )
            loaded2 = load_manifest(temp_path)
            self.assertEqual(loaded2.datasets["usda"].import_status, STATUS_VERIFIED)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_record_success_and_failure(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            manifest = create_initial_manifest()
            save_manifest(manifest, temp_path)

            # Record success
            record_ingestion_success(
                dataset_key="foodcom",
                imported_counts={"recipes": 25000, "interactions": 100000},
                path=temp_path,
            )
            loaded = load_manifest(temp_path)
            self.assertEqual(loaded.datasets["foodcom"].import_status, STATUS_COMPLETED)
            self.assertEqual(loaded.datasets["foodcom"].imported_row_counts["recipes"], 25000)
            self.assertIsNotNone(loaded.datasets["foodcom"].last_successful_ingestion)
            self.assertIsNone(loaded.datasets["foodcom"].failure_record)

            # Record failure
            record_ingestion_failure(
                dataset_key="foodcom",
                step="batch_insert_ratings",
                error_message="Simulated connection timeout",
                path=temp_path,
            )
            loaded_fail = load_manifest(temp_path)
            self.assertEqual(loaded_fail.datasets["foodcom"].import_status, STATUS_FAILED)
            self.assertIsNotNone(loaded_fail.datasets["foodcom"].failure_record)
            self.assertEqual(loaded_fail.datasets["foodcom"].failure_record.step, "batch_insert_ratings")
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    unittest.main()

