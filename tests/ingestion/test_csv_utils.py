"""Unit tests for streaming CSV processing, batching, and error tracking."""

import tempfile
import unittest
from pathlib import Path

from ingestion.utils.csv_utils import (
    IngestionProgressTracker,
    batch_iterator,
    count_csv_rows,
    inspect_csv_header,
    stream_csv_dict,
    stream_csv_raw,
)


class TestCSVUtils(unittest.TestCase):

    def test_inspect_csv_header(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as f:
            f.write("id,title,prep_time,ingredients\n")
            f.write("1,Pancakes,15,['flour', 'milk']\n")
            temp_path = Path(f.name)

        try:
            headers = inspect_csv_header(temp_path)
            self.assertEqual(headers, ["id", "title", "prep_time", "ingredients"])
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_count_csv_rows(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as f:
            f.write("id,title\n")
            for i in range(150):
                f.write(f"{i},Recipe {i}\n")
            temp_path = Path(f.name)

        try:
            row_count = count_csv_rows(temp_path, has_header=True)
            self.assertEqual(row_count, 150)

            # Test without header deduction
            total_lines = count_csv_rows(temp_path, has_header=False)
            self.assertEqual(total_lines, 151)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_stream_csv_dict(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as f:
            f.write("id,title,rating\n")
            f.write("101,Waffles,4.5\n")
            f.write("102,Omelette,5.0\n")
            temp_path = Path(f.name)

        try:
            records = list(stream_csv_dict(temp_path))
            self.assertEqual(len(records), 2)
            # First data row is CSV line 2
            self.assertEqual(records[0][0], 2)
            self.assertEqual(records[0][1]["title"], "Waffles")
            self.assertEqual(records[1][0], 3)
            self.assertEqual(records[1][1]["title"], "Omelette")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_batch_iterator(self):
        items = list(range(10))
        batches = list(batch_iterator(items, batch_size=3))
        self.assertEqual(len(batches), 4)
        self.assertEqual(batches[0], [0, 1, 2])
        self.assertEqual(batches[1], [3, 4, 5])
        self.assertEqual(batches[2], [6, 7, 8])
        self.assertEqual(batches[3], [9])

        # Test invalid batch size
        with self.assertRaises(ValueError):
            list(batch_iterator(items, batch_size=0))

    def test_progress_tracker_and_rejections(self):
        tracker = IngestionProgressTracker(
            dataset_name="food_com",
            file_name="RAW_recipes.csv",
        )

        tracker.record_accepted()
        tracker.record_accepted()
        tracker.record_rejected(
            line_number=45,
            reason="Missing recipe ID in raw row",
            sample=",,15,[]",
        )

        summary = tracker.summary()
        self.assertEqual(summary["total_read"], 3)
        self.assertEqual(summary["accepted"], 2)
        self.assertEqual(summary["rejected"], 1)
        self.assertEqual(len(summary["sample_rejections"]), 1)
        self.assertEqual(summary["sample_rejections"][0]["line"], 45)


if __name__ == "__main__":
    unittest.main()

