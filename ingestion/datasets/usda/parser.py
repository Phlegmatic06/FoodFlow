"""USDA FoodData Central Parser & Archive Source Handler

Provides safe streaming access to USDA CSV files from either:
  1. Official downloaded ZIP archives (via python zipfile without disk extraction).
  2. Extracted CSV directory trees.

Implements strict type coercion, NULL normalization, and whitespace cleanup.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

from ingestion.utils.checksums import compute_file_sha256, format_bytes
from ingestion.utils.csv_utils import configure_csv_limits


configure_csv_limits()

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class USDAParseError(Exception):
    """Raised when an unrecoverable structural or archive error occurs."""
    pass


# -----------------------------------------------------------------------------
# Type Coercion & Normalization Utilities
# -----------------------------------------------------------------------------
def clean_text(val: Any) -> Optional[str]:
    """Clean and strip text, converting empty or whitespace strings to None."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def parse_int(val: Any, field_name: str = "field") -> Optional[int]:
    """Parse integer, returning None if empty or raising ValueError if invalid."""
    cleaned = clean_text(val)
    if cleaned is None:
        return None
    try:
        # Handles numbers like "100.0" or "100"
        return int(float(cleaned))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid integer value for {field_name}: {val!r}") from e


def parse_float(val: Any, field_name: str = "field") -> Optional[float]:
    """Parse floating-point/numeric value, returning None if empty or raising ValueError."""
    cleaned = clean_text(val)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid numeric value for {field_name}: {val!r}") from e


def parse_date(val: Any, field_name: str = "field") -> Optional[str]:
    """Validate and return YYYY-MM-DD date string, or None if empty."""
    cleaned = clean_text(val)
    if cleaned is None:
        return None
    # If datetime string like "2020-04-01 00:00:00", take date portion
    if " " in cleaned:
        cleaned = cleaned.split(" ")[0].strip()
    if not DATE_PATTERN.match(cleaned):
        raise ValueError(f"Invalid date format (expected YYYY-MM-DD) for {field_name}: {val!r}")
    return cleaned


# -----------------------------------------------------------------------------
# Source Abstraction: Directory or ZIP Archive
# -----------------------------------------------------------------------------
class USDASource:
    """Encapsulates a USDA CSV distribution stored as a directory or ZIP file.
    
    Permits lazy streaming of CSV members directly from ZIP archives without
    extracting multi-hundred megabyte archives to disk.
    """

    def __init__(self, source_path: Path):
        self.source_path = Path(source_path).resolve()
        if not self.source_path.exists():
            raise FileNotFoundError(f"USDA source path not found: {self.source_path}")

        self.is_zip = self.source_path.is_file() and zipfile.is_zipfile(self.source_path)
        self.is_dir = self.source_path.is_dir()

        if not self.is_zip and not self.is_dir:
            raise ValueError(
                f"Source must be a valid directory or ZIP archive. Got: {self.source_path}"
            )

        self._file_map: Dict[str, str] = self._discover_members()

    def _discover_members(self) -> Dict[str, str]:
        """Map canonical filenames (e.g. 'food.csv') to internal member paths."""
        mapping: Dict[str, str] = {}
        if self.is_zip:
            with zipfile.ZipFile(self.source_path, "r") as z:
                for member in z.namelist():
                    # Ignore directory entries and macosx metadata
                    if member.endswith("/") or "__MACOSX" in member:
                        continue
                    basename = Path(member).name.lower()
                    if basename.endswith(".csv"):
                        mapping[basename] = member
        else:
            # Directory scan (searches root and one level of subdirectories)
            for path in self.source_path.rglob("*.csv"):
                if path.is_file():
                    basename = path.name.lower()
                    # Prefer top-level file if duplicate basenames exist
                    if basename not in mapping:
                        mapping[basename] = str(path)
        return mapping

    def has_file(self, canonical_name: str) -> bool:
        """Check if a canonical CSV file (e.g. 'food.csv') is available in the source."""
        return canonical_name.lower() in self._file_map

    def list_available_files(self) -> List[str]:
        """Return list of available canonical CSV filenames."""
        return sorted(list(self._file_map.keys()))

    def get_source_metadata(self) -> Tuple[int, str]:
        """Return total size in bytes and SHA-256 hash of the archive or primary files."""
        if self.is_zip:
            return self.source_path.stat().st_size, compute_file_sha256(self.source_path)
        # For directory, sum file sizes and compute combined hash of primary files
        total_size = sum(Path(p).stat().st_size for p in self._file_map.values())
        return total_size, "directory_distribution"

    def open_csv_stream(
        self,
        canonical_name: str,
        encoding: str = "utf-8",
    ) -> Generator[Tuple[int, Dict[str, str]], None, None]:
        """Stream CSV rows as dictionaries from the ZIP member or directory file.
        
        Yields (line_number, row_dict) lazily.
        """
        canonical = canonical_name.lower()
        if canonical not in self._file_map:
            raise FileNotFoundError(
                f"Expected CSV member '{canonical_name}' not found in source '{self.source_path}'"
            )

        internal_path = self._file_map[canonical]

        if self.is_zip:
            with zipfile.ZipFile(self.source_path, "r") as z:
                with z.open(internal_path, "r") as raw_stream:
                    text_stream = io.TextIOWrapper(
                        raw_stream,
                        encoding=encoding,
                        errors="replace",
                        newline="",
                    )
                    reader = csv.DictReader(text_stream)
                    line_num = 1
                    for row in reader:
                        line_num += 1
                        yield line_num, row
        else:
            file_path = Path(internal_path)
            with open(file_path, "r", encoding=encoding, errors="replace", newline="") as text_stream:
                reader = csv.DictReader(text_stream)
                line_num = 1
                for row in reader:
                    line_num += 1
                    yield line_num, row

    def inspect_headers(self, canonical_name: str, encoding: str = "utf-8") -> List[str]:
        """Return column header names for a canonical CSV member."""
        canonical = canonical_name.lower()
        if canonical not in self._file_map:
            raise FileNotFoundError(
                f"Expected CSV member '{canonical_name}' not found in source '{self.source_path}'"
            )

        internal_path = self._file_map[canonical]

        if self.is_zip:
            with zipfile.ZipFile(self.source_path, "r") as z:
                with z.open(internal_path, "r") as raw_stream:
                    text_stream = io.TextIOWrapper(
                        raw_stream,
                        encoding=encoding,
                        errors="replace",
                        newline="",
                    )
                    reader = csv.reader(text_stream)
                    for row in reader:
                        if row:
                            return [c.strip() for c in row]
        else:
            with open(Path(internal_path), "r", encoding=encoding, errors="replace", newline="") as text_stream:
                reader = csv.reader(text_stream)
                for row in reader:
                    if row:
                        return [c.strip() for c in row]
        return []

