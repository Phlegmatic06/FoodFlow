"""Ingredient categorization and quantity aggregation for shopping lists."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

CATEGORY_PRODUCE = "Produce"
CATEGORY_MEAT = "Meat & Seafood"
CATEGORY_DAIRY = "Dairy & Refrigerated"
CATEGORY_PANTRY = "Pantry & Dry Goods"
CATEGORY_SPICES = "Spices & Seasonings"
CATEGORY_BAKERY = "Bakery & Grains"
CATEGORY_OTHER = "Other"

# Keyword heuristics for supermarket category classification
PRODUCE_KEYWORDS = {
    "onion", "garlic", "shallot", "scallion", "chive", "leek",
    "tomato", "potato", "carrot", "celery", "bell pepper", "pepper", "chili",
    "jalapeno", "habanero", "spinach", "kale", "lettuce", "cabbage",
    "broccoli", "cauliflower", "zucchini", "squash", "cucumber", "eggplant",
    "mushroom", "avocado", "lemon", "lime", "orange", "apple", "banana",
    "berry", "strawberries", "blueberries", "basil", "parsley", "cilantro",
    "rosemary", "thyme", "mint", "ginger", "corn", "peas", "asparagus",
    "green beans", "salad", "herbs",
}

MEAT_KEYWORDS = {
    "chicken", "beef", "pork", "steak", "turkey", "lamb", "duck",
    "salmon", "tuna", "cod", "shrimp", "prawn", "crab", "lobster",
    "fish", "bacon", "sausage", "ham", "pancetta", "prosciutto",
    "ground beef", "ground turkey", "ground pork", "fillet", "breast", "thigh",
}

DAIRY_KEYWORDS = {
    "milk", "cream", "butter", "cheese", "parmesan", "cheddar", "mozzarella",
    "ricotta", "feta", "yogurt", "egg", "eggs", "sour cream", "cream cheese",
    "buttermilk", "heavy cream", "whipping cream", "ghee", "margarine",
}

SPICE_KEYWORDS = {
    "salt", "black pepper", "white pepper", "cumin", "paprika", "oregano",
    "cinnamon", "nutmeg", "cayenne", "curry powder", "turmeric", "coriander",
    "cardamom", "clove", "allspice", "bay leaf", "bay leaves", "red pepper flakes",
    "garlic powder", "onion powder", "vanilla", "vanilla extract",
}

BAKERY_KEYWORDS = {
    "bread", "roll", "rolls", "bun", "buns", "tortilla", "tortillas",
    "bagel", "bagels", "pita", "croissant", "crust", "baguette",
}

PANTRY_KEYWORDS = {
    "flour", "sugar", "brown sugar", "powdered sugar", "rice", "pasta",
    "spaghetti", "noodles", "olive oil", "vegetable oil", "canola oil",
    "sesame oil", "vinegar", "balsamic vinegar", "soy sauce", "honey",
    "maple syrup", "broth", "stock", "chicken broth", "beef broth",
    "vegetable broth", "canned tomatoes", "tomato paste", "tomato sauce",
    "black beans", "kidney beans", "chickpeas", "lentils", "oats",
    "rolled oats", "baking powder", "baking soda", "yeast", "cornstarch",
    "mayonnaise", "mustard", "ketchup", "peanut butter", "jam", "jelly",
}


def classify_ingredient_category(ingredient_name: str) -> str:
    """Classify an ingredient into a standard supermarket category using keyword heuristics."""
    name_lower = ingredient_name.lower().strip()

    # Exact or word boundary match against keyword groups
    for word in SPICE_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", name_lower):
            return CATEGORY_SPICES

    for word in DAIRY_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", name_lower):
            return CATEGORY_DAIRY

    for word in MEAT_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", name_lower):
            return CATEGORY_MEAT

    for word in PRODUCE_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", name_lower):
            return CATEGORY_PRODUCE

    for word in BAKERY_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", name_lower):
            return CATEGORY_BAKERY

    for word in PANTRY_KEYWORDS:
        if re.search(r"\b" + re.escape(word) + r"\b", name_lower):
            return CATEGORY_PANTRY

    return CATEGORY_OTHER


def aggregate_shopping_ingredients(
    raw_ingredients: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Consolidates raw recipe ingredients across meal plan slots.

    Aggregation rules:
    - Normalizes ingredient display names.
    - If multiple entries share the exact same clean name and compatible units (e.g., 'cup' + 'cup'),
      sum the numerical quantities.
    - If units differ, are missing, or are incompatible, keep as separate entries to prevent
      erroneous conversions.
    """
    aggregated: List[Dict[str, Any]] = []
    # Key: (clean_name_lower, unit_lower)
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for item in raw_ingredients:
        raw_name = (item.get("name") or item.get("raw_text") or "").strip()
        if not raw_name:
            continue

        clean_name = re.sub(r"^[0-9\./\s]+", "", raw_name).strip() or raw_name
        qty = item.get("amount")
        unit = (item.get("unit") or "").strip().lower()

        try:
            numeric_qty = float(qty) if qty is not None else None
        except (ValueError, TypeError):
            numeric_qty = None

        group_key = (clean_name.lower(), unit)

        if numeric_qty is not None and unit and group_key in grouped:
            # Compatible unit and name -> aggregate
            grouped[group_key]["total_qty"] += numeric_qty
        else:
            # New group or cannot aggregate
            entry = {
                "ingredient_name": clean_name,
                "total_qty": numeric_qty,
                "unit": unit,
                "category": classify_ingredient_category(clean_name),
            }
            if numeric_qty is not None and unit:
                grouped[group_key] = entry
            aggregated.append(entry)

    # Format quantity_display for all unique items
    results: List[Dict[str, Any]] = []
    for item in aggregated:
        tot = item.get("total_qty")
        u = item.get("unit")
        if tot is not None and tot > 0:
            formatted_tot = f"{tot:.1f}".rstrip("0").rstrip(".")
            qty_display = f"{formatted_tot} {u}".strip() if u else formatted_tot
        else:
            qty_display = None

        results.append(
            {
                "ingredient_name": item["ingredient_name"],
                "quantity_display": qty_display,
                "category": item["category"],
            }
        )

    # Deterministic sort: category then ingredient_name
    category_order = [
        CATEGORY_PRODUCE,
        CATEGORY_MEAT,
        CATEGORY_DAIRY,
        CATEGORY_PANTRY,
        CATEGORY_BAKERY,
        CATEGORY_SPICES,
        CATEGORY_OTHER,
    ]
    results.sort(
        key=lambda x: (
            category_order.index(x["category"]) if x["category"] in category_order else 99,
            x["ingredient_name"].lower(),
        )
    )
    return results

