"""Strict validation for canonical ingredient taxonomy seeds."""

from __future__ import annotations

import re
from typing import List, Set

from ingestion.taxonomy.definitions import CanonicalIngredientSeed

ALLOWED_CATEGORIES: Set[str] = {
    "Produce",
    "Dairy & Refrigerated",
    "Pantry & Dry Goods",
    "Bakery & Grains",
    "Meat & Seafood",
    "Spices & Seasonings",
}

COMPOUND_PATTERN = re.compile(r'\b(and|&|or)\b', re.IGNORECASE)


class TaxonomyValidationError(Exception):
    """Raised when canonical seed definitions violate integrity rules."""
    pass


def validate_seed_package(seed: List[CanonicalIngredientSeed]) -> None:
    """Validate canonical ingredient seed definitions against strict integrity constraints.

    Enforces:
    1. Non-empty seed and non-empty valid names.
    2. Valid categorical assignments from ALLOWED_CATEGORIES.
    3. Prohibition of compound phrases containing conjunctions ('and', '&', 'or').
    4. Canonical name uniqueness across all entries.
    5. Synonym uniqueness across all entries.
    6. Disjointness between canonical names and synonyms (no alias matches any canonical name).
    7. Mandatory identity distinctions (flour, milk, garlic, tomato, pepper, butter, herbs).
    """
    if not seed:
        raise TaxonomyValidationError("Canonical seed list cannot be empty.")

    canonical_names: Set[str] = set()
    all_aliases: Set[str] = set()

    for item in seed:
        # 1. Name validation
        if not item.name or not item.name.strip():
            raise TaxonomyValidationError("Canonical ingredient name cannot be empty.")
        norm_name = item.name.strip().lower()
        if norm_name != item.name:
            raise TaxonomyValidationError(
                f"Canonical ingredient name '{item.name}' must be lowercase and trimmed."
            )
        if COMPOUND_PATTERN.search(norm_name):
            raise TaxonomyValidationError(
                f"Canonical ingredient '{norm_name}' contains compound conjunctions."
            )

        if norm_name in canonical_names:
            raise TaxonomyValidationError(
                f"Duplicate canonical ingredient name detected: '{norm_name}'."
            )
        canonical_names.add(norm_name)

        # 2. Category validation
        if item.category not in ALLOWED_CATEGORIES:
            raise TaxonomyValidationError(
                f"Ingredient '{norm_name}' has invalid category '{item.category}'. "
                f"Allowed: {sorted(ALLOWED_CATEGORIES)}"
            )

        # 3. Synonym validation
        seen_item_aliases: Set[str] = set()
        for alias in item.aliases:
            if not alias or not alias.strip():
                raise TaxonomyValidationError(
                    f"Empty alias found in canonical ingredient '{norm_name}'."
                )
            norm_alias = alias.strip().lower()
            if norm_alias != alias:
                raise TaxonomyValidationError(
                    f"Alias '{alias}' for '{norm_name}' must be lowercase and trimmed."
                )
            if COMPOUND_PATTERN.search(norm_alias):
                raise TaxonomyValidationError(
                    f"Alias '{norm_alias}' for '{norm_name}' contains compound conjunctions."
                )
            if norm_alias in seen_item_aliases:
                raise TaxonomyValidationError(
                    f"Duplicate alias '{norm_alias}' defined for same ingredient '{norm_name}'."
                )
            seen_item_aliases.add(norm_alias)

            if norm_alias in all_aliases:
                raise TaxonomyValidationError(
                    f"Alias collision: '{norm_alias}' is defined for multiple canonical ingredients."
                )
            all_aliases.add(norm_alias)

    # 4. Synonym vs Canonical disjointness
    collision = canonical_names.intersection(all_aliases)
    if collision:
        raise TaxonomyValidationError(
            f"Alias collides with canonical ingredient name: {sorted(collision)}"
        )

    # 5. Mandatory identity distinctions
    required_distinct_groups = [
        ("flour", "all-purpose flour"),
        ("milk", "whole milk"),
        ("milk", "skim milk"),
        ("garlic", "garlic powder"),
        ("tomato", "tomato paste"),
        ("tomato", "tomato sauce"),
        ("pepper", "black pepper"),
        ("pepper", "white pepper"),
        ("butter", "unsalted butter"),
        ("butter", "salted butter"),
        ("oregano", "dried oregano"),
        ("basil", "dried basil"),
        ("parsley", "dried parsley"),
        ("thyme", "dried thyme"),
        ("rosemary", "dried rosemary"),
    ]
    for left, right in required_distinct_groups:
        if left not in canonical_names:
            raise TaxonomyValidationError(f"Mandatory distinct ingredient missing: '{left}'")
        if right not in canonical_names:
            raise TaxonomyValidationError(f"Mandatory distinct ingredient missing: '{right}'")

    # 6. Compound phrases must never exist
    forbidden_terms = ["salt and pepper", "salt and black pepper", "salt & pepper"]
    for ft in forbidden_terms:
        if ft in canonical_names or ft in all_aliases:
            raise TaxonomyValidationError(f"Forbidden compound term found in taxonomy: '{ft}'")

