"""RecipeNLG Dataset Parser & Safe Evaluation Utilities

Provides memory-bounded streaming access to RecipeNLG raw files:
  - full_dataset.csv (or compressed full_dataset.zip)

Implements:
  - Direct ZIP archive streaming via zipfile without extraction.
  - Direct CSV file and directory discovery.
  - UTF-8 with BOM handling (utf-8-sig).
  - Safe list extraction (JSON first, then ast.literal_eval, NEVER eval()).
  - Conservative ingredient quantity and unit extraction.
  - High CSV field size limits for long direction steps.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import re
import zipfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

from ingestion.config import CSV_FIELD_SIZE_LIMIT
from ingestion.logging_config import get_logger
from ingestion.utils.checksums import compute_file_sha256
from ingestion.utils.csv_utils import configure_csv_limits


configure_csv_limits()
logger = get_logger("recipenlg.parser")


class RecipeNLGParseError(Exception):
    """Raised when an unrecoverable structural, archive, or list parsing error occurs."""
    pass


# -----------------------------------------------------------------------------
# Conservative Quantity & Unit Extraction
# -----------------------------------------------------------------------------
# Standard culinary units recognized in English recipes with normalization
UNIT_NORMALIZATION_MAP: Dict[str, str] = {
    "cup": "cup", "cups": "cup", "c": "cup",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp", "tbs": "tbsp", "tb": "tbsp",
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp", "ts": "tsp",
    "ounce": "oz", "ounces": "oz", "oz": "oz",
    "pound": "lb", "pounds": "lb", "lb": "lb", "lbs": "lb",
    "gram": "g", "grams": "g", "g": "g",
    "kilogram": "kg", "kilograms": "kg", "kg": "kg",
    "milliliter": "ml", "milliliters": "ml", "ml": "ml",
    "liter": "l", "liters": "l", "l": "l",
    "pint": "pint", "pints": "pint", "pt": "pint",
    "quart": "quart", "quarts": "quart", "qt": "quart",
    "gallon": "gallon", "gallons": "gallon", "gal": "gallon",
    "pinch": "pinch", "pinches": "pinch",
    "dash": "dash", "dashes": "dash",
    "clove": "clove", "cloves": "clove",
    "can": "can", "cans": "can",
    "package": "package", "packages": "package", "pkg": "package", "pkgs": "package",
    "packet": "packet", "packets": "packet",
    "slice": "slice", "slices": "slice",
    "piece": "piece", "pieces": "piece",
    "stalk": "stalk", "stalks": "stalk",
    "sprig": "sprig", "sprigs": "sprig",
    "head": "head", "heads": "head",
    "bunch": "bunch", "bunches": "bunch",
    "bottle": "bottle", "bottles": "bottle",
    "jar": "jar", "jars": "jar",
    "stick": "stick", "sticks": "stick",
}

# Regex for leading quantity: integer, decimal, fraction (1/2), or mixed fraction (1 1/2)
QUANTITY_UNIT_PATTERN = re.compile(
    r"^(?P<qty>(?:\d+\s+)?\d+/\d+|\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z]+)?(?:\s+(?P<rest>.*))?$"
)


def parse_ingredient_amount_and_unit(raw_text: str) -> Tuple[Optional[float], Optional[str]]:
    """Conservatively parse leading numeric quantity and unit from an ingredient string.
    
    Returns (quantity_float, unit_str). If unparseable or ambiguous, returns (None, None).
    Examples:
        '2 cups all-purpose flour' -> (2.0, 'cup')
        '1 1/2 tsp vanilla extract' -> (1.5, 'tsp')
        '1/4 lb butter' -> (0.25, 'lb')
        'salt and black pepper to taste' -> (None, None)
    """
    if not raw_text:
        return None, None
    s = raw_text.strip()
    match = QUANTITY_UNIT_PATTERN.match(s)
    if not match:
        return None, None

    qty_str = match.group("qty")
    unit_str = match.group("unit")

    # 1. Parse numeric quantity
    quantity: Optional[float] = None
    try:
        if " " in qty_str:
            whole, frac = qty_str.split(" ", 1)
            quantity = float(int(whole) + float(Fraction(frac)))
        elif "/" in qty_str:
            quantity = float(Fraction(qty_str))
        else:
            quantity = float(qty_str)
    except (ValueError, ZeroDivisionError):
        return None, None

    # Check for reasonable culinary quantity bounds (e.g. 0 < qty <= 10,000)
    if quantity <= 0 or quantity > 10000:
        return None, None

    # 2. Validate unit
    unit: Optional[str] = None
    if unit_str:
        norm_unit = unit_str.lower().strip()
        unit = UNIT_NORMALIZATION_MAP.get(norm_unit)

    return round(quantity, 3), unit


# -----------------------------------------------------------------------------
# Safe List and String Parsing (JSON first, fallback ast.literal_eval, NEVER eval)
# -----------------------------------------------------------------------------
def safe_parse_list(val: Any, field_name: str = "list", line_number: int = 1) -> List[str]:
    """Safely parse a serialized list string (JSON or Python literal).
    
    Strictly verifies that:
      - Root structure is a list.
      - Every element in the list is a non-empty string.
      - Code injection vectors are completely prevented.
    """
    if val is None:
        return []
    s = str(val).strip()
    if not s or s == "[]":
        return []

    # Structure pre-check: must be wrapped in [ ... ]
    if not (s.startswith("[") and s.endswith("]")):
        raise RecipeNLGParseError(
            f"Line {line_number}: Field '{field_name}' does not appear to be a list: {s[:60]!r}"
        )

    parsed: Optional[List[Any]] = None

    # Step 1: Attempt standard JSON parsing
    try:
        candidate = json.loads(s)
        if isinstance(candidate, list):
            parsed = candidate
    except (json.JSONDecodeError, ValueError):
        parsed = None

    # Step 2: Fallback to ast.literal_eval for Python-style lists (e.g. single quotes)
    if parsed is None:
        try:
            candidate = ast.literal_eval(s)
            if isinstance(candidate, list):
                parsed = candidate
            else:
                raise RecipeNLGParseError(
                    f"Line {line_number}: Field '{field_name}' evaluated to {type(candidate).__name__}, expected list."
                )
        except (SyntaxError, ValueError, TypeError, MemoryError) as e:
            raise RecipeNLGParseError(
                f"Line {line_number}: Failed to parse '{field_name}' list: {e}"
            ) from e

    # Step 3: Validate that all elements are strings
    validated_strings: List[str] = []
    for idx, item in enumerate(parsed):
        if not isinstance(item, str):
            raise RecipeNLGParseError(
                f"Line {line_number}: Element {idx} in '{field_name}' is not a string (got {type(item).__name__}): {item!r}"
            )
        cleaned = item.replace("\x00", "").strip()
        if cleaned:
            validated_strings.append(cleaned)

    return validated_strings


def clean_text(val: Any) -> Optional[str]:
    """Clean string whitespace and null characters, returning None if empty."""
    if val is None:
        return None
    s = str(val).replace("\x00", "").strip()
    return s if s else None


KNOWN_RECIPENLG_CSV_BASENAMES: Tuple[str, ...] = (
    "recipenlg_dataset.csv",
    "full_dataset.csv",
    "recipe_nlg.csv",
    "recipes.csv",
)


# -----------------------------------------------------------------------------
# Source Abstraction: ZIP Archive, Directory, or Direct CSV File
# -----------------------------------------------------------------------------
class RecipeNLGSource:
    """Provides streaming access to RecipeNLG files from a ZIP archive, directory, or CSV file."""

    def __init__(self, source_path: Path):
        self.source_path = Path(source_path).resolve()
        if not self.source_path.exists():
            raise FileNotFoundError(f"RecipeNLG source path not found: {self.source_path}")

        self.is_zip = self.source_path.is_file() and zipfile.is_zipfile(self.source_path)
        self.is_single_csv = self.source_path.is_file() and not self.is_zip and self.source_path.suffix.lower() == ".csv"
        self.is_dir = self.source_path.is_dir()

        if not (self.is_zip or self.is_single_csv or self.is_dir):
            raise ValueError(
                f"Source must be a valid directory, CSV file, or ZIP archive. Got: {self.source_path}"
            )

        self._file_map: Dict[str, str] = self._discover_members()

    def _discover_members(self) -> Dict[str, str]:
        """Map canonical filename 'full_dataset.csv' to member paths."""
        mapping: Dict[str, str] = {}
        if self.is_single_csv:
            mapping["full_dataset.csv"] = str(self.source_path)
        elif self.is_zip:
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

    def has_file(self, canonical_name: str = "full_dataset.csv") -> bool:
        """Check if a canonical CSV file is available (case-insensitive)."""
        if self.is_single_csv:
            return True
        canonical = canonical_name.lower()
        if canonical in self._file_map:
            return True
        for candidate in KNOWN_RECIPENLG_CSV_BASENAMES:
            if candidate in self._file_map:
                return True
        return bool(self._file_map)

    def list_available_files(self) -> List[str]:
        """Return list of discovered CSV filenames."""
        return sorted(list(self._file_map.keys()))

    def get_source_metadata(self) -> Tuple[int, str]:
        """Return size in bytes and SHA-256 hash of the archive or primary file."""
        if self.source_path.is_file():
            return self.source_path.stat().st_size, compute_file_sha256(self.source_path)
        # Directory distribution
        total_size = sum(Path(p).stat().st_size for p in self._file_map.values())
        return total_size, "directory_distribution"

    def inspect_headers(self, canonical_name: str = "full_dataset.csv", encoding: str = "utf-8-sig") -> List[str]:
        """Inspect and return the column header list for the CSV source."""
        internal_key = self._resolve_internal_key(canonical_name)

        if self.is_zip:
            with zipfile.ZipFile(self.source_path, "r") as z:
                with z.open(internal_key, "r") as raw_stream:
                    text_stream = io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace", newline="")
                    reader = csv.reader(text_stream)
                    for row in reader:
                        if row:
                            return [c.strip() for c in row]
        else:
            with open(Path(internal_key), "r", encoding=encoding, errors="replace", newline="") as text_stream:
                reader = csv.reader(text_stream)
                for row in reader:
                    if row:
                        return [c.strip() for c in row]
        return []

    def open_csv_stream(
        self,
        canonical_name: str = "full_dataset.csv",
        encoding: str = "utf-8-sig",
    ) -> Generator[Tuple[int, Dict[str, str]], None, None]:
        """Stream CSV rows as dictionaries lazily from the source.
        
        Yields (line_number, row_dict). Line number starts at 2 for the first data row.
        """
        internal_key = self._resolve_internal_key(canonical_name)

        if self.is_zip:
            with zipfile.ZipFile(self.source_path, "r") as z:
                with z.open(internal_key, "r") as raw_stream:
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
            file_path = Path(internal_key)
            with open(file_path, "r", encoding=encoding, errors="replace", newline="") as text_stream:
                reader = csv.DictReader(text_stream)
                line_num = 1
                for row in reader:
                    line_num += 1
                    yield line_num, row

    def _resolve_internal_key(self, canonical_name: str) -> str:
        """Resolve internal file map entry."""
        if self.is_single_csv:
            return str(self.source_path)
        canonical = canonical_name.lower()
        if canonical in self._file_map:
            return self._file_map[canonical]
        for candidate in KNOWN_RECIPENLG_CSV_BASENAMES:
            if candidate in self._file_map:
                logger.info(f"Target '{canonical_name}' resolved to known RecipeNLG member '{candidate}'.")
                return self._file_map[candidate]
        if self._file_map:
            # Pick first available CSV if specific name not found
            first_key = next(iter(self._file_map.keys()))
            logger.info(f"Target '{canonical_name}' not found by exact name. Using '{first_key}'.")
            return self._file_map[first_key]
        raise FileNotFoundError(
            f"No CSV files found in source '{self.source_path}'. Available: {self.list_available_files()}"
        )
