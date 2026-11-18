"""Unit tests for streaming checksum and file metadata utilities."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from ingestion.utils.checksums import (
    compute_bytes_sha256,
    compute_file_sha256,
    format_bytes,
    get_file_metadata,
    verify_file_sha256,
)


class TestChecksums(unittest.TestCase):

    def test_compute_bytes_sha256(self):
        sample = b"NutriPod streaming ingestion test payload"
        expected = hashlib.sha256(sample).hexdigest().lower()
        actual = compute_bytes_sha256(sample)
        self.assertEqual(actual, expected)

    def test_streaming_file_sha256(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # Write 2.5 MB of repeatable binary data to test multi-chunk streaming
            chunk = b"A" * 1024 * 1024  # 1 MB
            f.write(chunk)
            f.write(chunk)
            f.write(b"B" * (512 * 1024))  # 512 KB
            temp_path = Path(f.name)

        try:
            # Compute direct hash
            with open(temp_path, "rb") as rf:
                expected_hash = hashlib.sha256(rf.read()).hexdigest().lower()

            # Compute streaming hash with 64KB chunk size
            actual_hash = compute_file_sha256(temp_path, chunk_size=64 * 1024)
            self.assertEqual(actual_hash, expected_hash)

            # Test verify_file_sha256
            self.assertTrue(verify_file_sha256(temp_path, expected_hash))
            self.assertTrue(verify_file_sha256(temp_path, expected_hash.upper()))  # Case insensitive
            self.assertFalse(verify_file_sha256(temp_path, "0" * 64))  # Mismatched hash

            # Test get_file_metadata
            size, hash_val = get_file_metadata(temp_path)
            self.assertEqual(size, (2 * 1024 * 1024) + (512 * 1024))
            self.assertEqual(hash_val, expected_hash)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_missing_file_handling(self):
        missing_path = Path("/path/to/nonexistent/file.csv")
        self.assertFalse(verify_file_sha256(missing_path, "any_hash"))
        with self.assertRaises(FileNotFoundError):
            get_file_metadata(missing_path)

    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(1024), "1.00 KB")
        self.assertEqual(format_bytes(1024 * 1024), "1.00 MB")
        self.assertEqual(format_bytes(1024 * 1024 * 1024 * 2), "2.00 GB")


if __name__ == "__main__":
    unittest.main()

