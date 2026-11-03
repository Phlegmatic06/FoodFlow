"""Food.com Dataset Parser & Safe Evaluation Utilities

Provides memory-bounded streaming access to Food.com raw files:
  - RAW_recipes.csv
  - RAW_interactions.csv

Implements safe ast.literal_eval list extraction, nutrition array parsing,
time validation (sentinel detection), and data-quality warnings.
"""

from __future__ import annotations

import ast
import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

from ingestion.logging_config import get_logger
from ingestion.utils.checksums import compute_file_sha256
from ingestion.utils.csv_utils import configure_csv_limits


configure_csv_limits()
logger = get_logger("foodcom.parser")

DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Food.com sentinel value constant for unrecorded / overflow duration
SENTINEL_MINUTES_THRESHOLD = 43200  # 30 days in minutes (43,200). Values beyond are implausible sentinels.


class FoodComParseError(Exception):
    """Raised when an unrecoverable structural or archive error occurs."""
    pass


# -----------------------------------------------------------------------------
# Safe List and Array Parsing (NEVER uses eval())
# -----------------------------------------------------------------------------
def safe_parse_python_list(val: Any, field_name: str = "list", line_number: int = 1) -> List[Any]:
    """Safely parse a stringified Python-style list using ast.literal_eval.
    
    Guarantees safety against code injection and validates that parsed
    output is strictly a list.
    """
    if val is None:
        return []
    s = str(val).strip()
    if not s or s == "[]":
        return []

    # Structure pre-check: must begin with [ and end with ]
    if not (s.startswith("[") and s.endswith("]")):
        raise FoodComParseError(
            f"Line {line_number}: Field '{field_name}' does not appear to be a stringified list: {s[:60]!r}"
        )

    try:
        parsed = ast.literal_eval(s)
        if not isinstance(parsed, list):
            raise FoodComParseError(f"Line {line_number}: Field '{field_name}' evaluated to {type(parsed)}, expected list.")
        return parsed
    except FoodComParseError:
        raise
    except (SyntaxError, ValueError, TypeError, MemoryError) as e:
        raise FoodComParseError(f"Line {line_number}: Failed to parse '{field_name}' list: {e}") from e


def parse_nutrition_array(val: Any, line_number: int = 1) -> Tuple[float, float, float, float, float, float, float]:
    """Parse the Food.com 7-element nutrition array:
    [calories (kcal), total_fat (%DV), sugar (%DV), sodium (%DV), protein (%DV), saturated_fat (%DV), carbohydrates (%DV)]
    
    Preserves raw %DV values verbatim. All numbers must be non-negative.
    """
    parsed_list = safe_parse_python_list(val, "nutrition", line_number)
    if len(parsed_list) != 7:
        raise FoodComParseError(
            f"Line {line_number}: Nutrition array must have exactly 7 elements, got {len(parsed_list)}: {val!r}"
        )

    coerced: List[float] = []
    for idx, elem in enumerate(parsed_list):
        try:
            num = float(elem)
            if num < 0:
                raise FoodComParseError(f"Element at index {idx} is negative: {num}")
            coerced.append(num)
        except (ValueError, TypeError) as e:
            raise FoodComParseError(
                f"Line {line_number}: Invalid numeric value at index {idx} of nutrition array: {elem!r}"
            ) from e

    return (
        coerced[0],  # raw_calories (kcal)
        coerced[1],  # raw_total_fat_pdv
        coerced[2],  # raw_sugar_pdv
        coerced[3],  # raw_sodium_pdv
        coerced[4],  # raw_protein_pdv
        coerced[5],  # raw_saturated_fat_pdv
        coerced[6],  # raw_carbohydrates_pdv
    )


def parse_time_minutes(val: Any, line_number: int = 1) -> Optional[int]:
    """Parse total duration in minutes.
    
    If the value is negative or exceeds the plausible threshold (e.g. 2147483647 or > 30 days),
    returns None and flags it rather than rejecting the entire recipe record.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None

    try:
        minutes = int(float(s))
    except (ValueError, TypeError):
        logger.warning(f"Line {line_number}: Unparseable minutes value: {val!r}. Storing as NULL.")
        return None

    if minutes < 0:
        logger.warning(f"Line {line_number}: Negative minutes value: {minutes}. Storing as NULL.")
        return None

    if minutes > SENTINEL_MINUTES_THRESHOLD:
        logger.warning(
            f"Line {line_number}: Implausible sentinel cooking time ({minutes:,} mins > {SENTINEL_MINUTES_THRESHOLD:,}). "
            f"Storing as NULL."
        )
        return None

    return minutes


def parse_date(val: Any) -> Optional[str]:
    """Validate and return YYYY-MM-DD date string, or None if empty/invalid."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if " " in s:
        s = s.split(" ")[0].strip()
    return s if DATE_PATTERN.match(s) else None


def clean_text(val: Any) -> Optional[str]:
    """Clean string whitespace and null characters, returning None if empty."""
    if val is None:
        return None
    s = str(val).replace("\x00", "").strip()
    return s if s else None


# -----------------------------------------------------------------------------
# Source Abstraction: Directory or ZIP Archive
# -----------------------------------------------------------------------------
class FoodComSource:
    """Provides streaming access to Food.com files from a directory or ZIP archive."""

    def __init__(self, source_path: Path):
        self.source_path = Path(source_path).resolve()
        if not self.source_path.exists():
            raise FileNotFoundError(f"Food.com source path not found: {self.source_path}")

        self.is_zip = self.source_path.is_file() and zipfile.is_zipfile(self.source_path)
        self.is_dir = self.source_path.is_dir()

        if not self.is_zip and not self.is_dir:
            raise ValueError(f"Source must be a valid directory or ZIP archive. Got: {self.source_path}")

        self._file_map: Dict[str, str] = self._discover_members()

    def _discover_members(self) -> Dict[str, str]:
        """Map canonical filenames ('raw_recipes.csv', 'raw_interactions.csv') to member paths."""
        mapping: Dict[str, str] = {}
        if self.is_zip:
            with zipfile.ZipFile(self.source_path, "r") as z:
                for member in z.namelist():
                    if member.endswith("/") or "__MACOSX" in member:
                        continue
                    basename = Path(member).name.lower()
                    if basename.endswith(".csv"):
                        mapping[basename] = member
        else:
            for path in self.source_path.rglob("*.csv"):
                if path.is_file():
                    basename = path.name.lower()
                    if basename not in mapping:
                        mapping[basename] = str(path)
        return mapping

    def has_file(self, canonical_name: str) -> bool:
        """Check if a canonical CSV file is available (case-insensitive)."""
        return canonical_name.lower() in self._file_map

    def list_available_files(self) -> List[str]:
        """Return list of discovered CSV filenames."""
        return sorted(list(self._file_map.keys()))

    def get_source_metadata(self) -> Tuple[int, str]:
        """Return size in bytes and SHA-256 hash of the archive or primary files."""
        if self.is_zip:
            return self.source_path.stat().st_size, compute_file_sha256(self.source_path)
        total_size = sum(Path(p).stat().st_size for p in self._file_map.values())
        return total_size, "directory_distribution"

    def open_csv_stream(
        self,
        canonical_name: str,
        encoding: str = "utf-8",
    ) -> Generator[Tuple[int, Dict[str, str]], None, None]:
        """Stream CSV rows as dictionaries lazily from the source."""
        canonical = canonical_name.lower()
        if canonical not in self._file_map:
            raise FileNotFoundError(
                f"Expected CSV member '{canonical_name}' not found in source '{self.source_path}'. "
                f"Available: {self.list_available_files()}"
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
        """Inspect and return the column header list for a canonical CSV member."""
        canonical = canonical_name.lower()
        if canonical not in self._file_map:
            raise FileNotFoundError(f"Expected CSV member '{canonical_name}' not found.")

        internal_path = self._file_map[canonical]

        if self.is_zip:
            with zipfile.ZipFile(self.source_path, "r") as z:
                with z.open(internal_path, "r") as raw_stream:
                    text_stream = io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace", newline="")
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
