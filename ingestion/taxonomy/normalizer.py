"""Text normalization and token cleaning utilities for ingredient taxonomy."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# Common cooking units for conservative prefix stripping
UNITS = [
    r'teaspoons?', r'tsp\.?',
    r'tablespoons?', r'tbsp\.?', r'tbs\.?', r'tb\.?',
    r'cups?', r'c\.?',
    r'ounces?', r'oz\.?',
    r'pounds?', r'lbs?\.?',
    r'grams?', r'g\.?',
    r'kilograms?', r'kg\.?',
    r'milliliters?', r'ml\.?',
    r'liters?', r'l\.?',
    r'pints?', r'pt\.?',
    r'quarts?', r'qt\.?',
    r'gallons?', r'gal\.?',
    r'cloves?',
    r'pinches?', r'pinch',
    r'dashes?', r'dash',
    r'packages?', r'pkgs?\.?', r'pkg\.?',
    r'cans?',
    r'bottles?',
    r'jars?',
    r'bunches?', r'bunch',
    r'slices?', r'slice',
    r'pieces?', r'piece',
    r'stalks?', r'stalk',
    r'ribs?', r'rib',
    r'heads?', r'head',
    r'sprigs?', r'sprig',
    r'sticks?', r'stick',
    r'envelopes?',
    r'bags?',
]

# Numeric patterns: fractions, decimals, mixed fractions, unicode fractions, ranges
NUM_PATTERN = r'(?:(?:\d+[\s\-]+)?\d+/\d+|\d+(?:\.\d+)?|[½⅓⅔¼¾⅛⅜⅝⅞]|\d+[\s\-]*to[\s\-]*\d+|\d+[\s\-]*\-[\s\-]*\d+)'
UNIT_OR = "|".join(UNITS)
PAREN_SIZE = rf'\(\s*{NUM_PATTERN}?\s*(?:{UNIT_OR})\s*\)'

PREFIX_PATTERN = re.compile(
    rf'^\s*(?:{NUM_PATTERN}\s*)?(?:{PAREN_SIZE}\s*)?(?:(?:{UNIT_OR})\s+)+(?:{PAREN_SIZE}\s*)?(?:of\s+)?',
    re.IGNORECASE,
)
NUM_ONLY_PREFIX = re.compile(
    rf'^\s*{NUM_PATTERN}\s+(?:of\s+)?',
    re.IGNORECASE,
)


def normalize_text(text: Optional[str]) -> str:
    """Normalize unicode and collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def strip_quantity_unit_prefix(text: Optional[str]) -> str:
    """Conservatively strip quantity and unit prefixes while preserving ingredient name."""
    norm = normalize_text(text)
    if not norm:
        return ""

    # Try stripping unit prefix: e.g. "1 tsp. salt" -> "salt", "2 cups flour" -> "flour"
    m = PREFIX_PATTERN.match(norm)
    if m:
        candidate = norm[m.end():].strip()
        if candidate:
            return candidate

    # Try stripping pure quantity prefix: e.g. "2 eggs" -> "eggs", "3 apples" -> "apples"
    m_num = NUM_ONLY_PREFIX.match(norm)
    if m_num:
        candidate = norm[m_num.end():].strip()
        if candidate:
            return candidate

    return norm


def clean_ingredient_token(text: Optional[str]) -> str:
    """Normalize text and remove surrounding punctuation."""
    norm = normalize_text(text)
    if not norm:
        return ""
    # Strip leading/trailing punctuation except alphanumeric
    norm = re.sub(r'^[^\w]+|[^\w]+$', '', norm)
    return norm

