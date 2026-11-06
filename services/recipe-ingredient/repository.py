"""Database repository layer for Recipe & Ingredient Service."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg
from psycopg import sql

# Common cooking units and packaging descriptors for conservative prefix stripping
_COOKING_UNITS = [
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

_NUM_PATTERN = r'(?:(?:\d+[\s\-]+)?\d+/\d+|\d+(?:\.\d+)?|[½⅓⅔¼¾⅛⅜⅝⅞]|\d+[\s\-]*to[\s\-]*\d+|\d+[\s\-]*\-[\s\-]*\d+)'
_UNIT_OR = "|".join(_COOKING_UNITS)
_PAREN_SIZE = rf'\(\s*{_NUM_PATTERN}?\s*(?:{_UNIT_OR})\s*\)'

_PREFIX_PATTERN = re.compile(
    rf'^\s*(?:{_NUM_PATTERN}\s*)?(?:{_PAREN_SIZE}\s*)?(?:(?:{_UNIT_OR})\s+)+(?:{_PAREN_SIZE}\s*)?(?:of\s+)?',
    re.IGNORECASE,
)
_NUM_ONLY_PREFIX = re.compile(
    rf'^\s*{_NUM_PATTERN}\s+(?:of\s+)?',
    re.IGNORECASE,
)
_COMPOUND_PATTERN = re.compile(
    r'(?:\band/or\b|\band\b|\bor\b|[&+,;/]|\s+-\s+)',
    re.IGNORECASE,
)


def _strip_quantity_unit_prefix(text: str) -> str:
    """Conservatively remove quantity and unit prefixes from user input."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFKC", text).lower().strip()
    norm = re.sub(r'\s+', ' ', norm)
    m = _PREFIX_PATTERN.match(norm)
    if m:
        c = norm[m.end():].strip()
        if c:
            return c
    m_num = _NUM_ONLY_PREFIX.match(norm)
    if m_num:
        c = norm[m_num.end():].strip()
        if c:
            return c
    return norm

from services.common.database import ServiceDatabaseManager
from services.recipe_ingredient.schemas import (
    IngredientCandidateItem,
    IngredientSuggestion,
    NormalizedIngredientResult,
    RecipeDetail,
    RecipeIngredientItem,
    RecipeInstructionItem,
    RecipeRawNutrition,
    RecipeSummary,
)


class RecipeRepository:
    """Repository handling SQL queries for the recipe catalogue and ingredient taxonomy."""

    def __init__(self, db_manager: ServiceDatabaseManager) -> None:
        self.db = db_manager

    def search_recipes(
        self,
        q: Optional[str] = None,
        cuisine: Optional[str] = None,
        tag: Optional[str] = None,
        diet: Optional[str] = None,
        max_time: Optional[int] = None,
        source_dataset: Optional[str] = None,
        sort: str = "relevance",
        page: int = 1,
        limit: int = 24,
    ) -> Tuple[List[RecipeSummary], int]:
        """Search and filter recipes with pagination and sorting."""
        where_clauses: List[str] = []
        where_params: List[Any] = []

        clean_q = q.strip() if q and q.strip() else None

        if clean_q:
            where_clauses.append("r.tsv_search @@ websearch_to_tsquery('english', %s)")
            where_params.append(clean_q)

        if cuisine and cuisine.strip():
            c_val = cuisine.strip()
            where_clauses.append(
                "(r.cuisine ILIKE %s OR EXISTS ("
                "SELECT 1 FROM recipe_catalog.recipe_tags rt "
                "WHERE rt.recipe_id = r.id AND LOWER(rt.tag) = LOWER(%s)"
                "))"
            )
            where_params.extend([c_val, c_val])

        if tag and tag.strip():
            t_val = tag.strip()
            where_clauses.append(
                "EXISTS (SELECT 1 FROM recipe_catalog.recipe_tags rt "
                "WHERE rt.recipe_id = r.id AND LOWER(rt.tag) = LOWER(%s))"
            )
            where_params.append(t_val)

        if diet and diet.strip():
            d_val = diet.strip()
            where_clauses.append(
                "EXISTS (SELECT 1 FROM recipe_catalog.recipe_tags rt "
                "WHERE rt.recipe_id = r.id AND LOWER(rt.tag) = LOWER(%s))"
            )
            where_params.append(d_val)

        if max_time is not None:
            where_clauses.append("r.total_time_minutes IS NOT NULL AND r.total_time_minutes <= %s")
            where_params.append(max_time)

        if source_dataset:
            where_clauses.append("r.source_dataset = %s")
            where_params.append(source_dataset)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Determine ORDER BY clause
        order_params: List[Any] = []
        if sort == "relevance":
            if clean_q:
                order_sql = "ts_rank(r.tsv_search, websearch_to_tsquery('english', %s)) DESC, r.id ASC"
                order_params.append(clean_q)
            else:
                order_sql = "r.id ASC"
        elif sort == "rating":
            order_sql = "rr.rating_average DESC NULLS LAST, rr.rating_count DESC, r.id ASC"
        elif sort == "time_asc":
            order_sql = "r.total_time_minutes ASC NULLS LAST, r.id ASC"
        elif sort == "time_desc":
            order_sql = "r.total_time_minutes DESC NULLS LAST, r.id ASC"
        else:
            order_sql = "r.id ASC"

        offset = (page - 1) * limit

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # 1. Total matching count
                count_query = f"SELECT count(*) FROM recipe_catalog.recipes r {where_sql};"
                cur.execute(count_query, where_params)
                row = cur.fetchone()
                total_items = row[0] if row else 0

                if total_items == 0:
                    return [], 0

                # 2. Page of recipe summaries
                data_query = f"""
                    SELECT r.id, r.source_dataset, r.source_id, r.title, r.description,
                           r.prep_time_minutes, r.cook_time_minutes, r.total_time_minutes,
                           r.servings, r.cuisine, r.source_url,
                           rr.rating_average, COALESCE(rr.rating_count, 0) AS rating_count,
                           ARRAY(
                               SELECT tag FROM recipe_catalog.recipe_tags rt
                               WHERE rt.recipe_id = r.id
                               LIMIT 5
                           ) AS tag_preview
                    FROM recipe_catalog.recipes r
                    LEFT JOIN recipe_catalog.recipe_ratings rr ON rr.recipe_id = r.id
                    {where_sql}
                    ORDER BY {order_sql}
                    LIMIT %s OFFSET %s;
                """
                all_params = list(where_params) + order_params + [limit, offset]
                cur.execute(data_query, all_params)
                rows = cur.fetchall()

                summaries: List[RecipeSummary] = []
                for r in rows:
                    avg_rating = float(r[11]) if r[11] is not None else None
                    summaries.append(
                        RecipeSummary(
                            id=r[0],
                            source_dataset=r[1],
                            source_id=r[2],
                            title=r[3],
                            description=r[4],
                            prep_time_minutes=r[5],
                            cook_time_minutes=r[6],
                            total_time_minutes=r[7],
                            servings=r[8],
                            cuisine=r[9],
                            source_url=r[10],
                            rating_average=avg_rating,
                            rating_count=int(r[12]),
                            tag_preview=list(r[13]) if r[13] else [],
                        )
                    )

                return summaries, total_items

    def get_recipe_detail(self, recipe_id: str) -> Optional[RecipeDetail]:
        """Fetch full recipe record with ordered ingredients, instructions, tags, ratings and nutrition."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # 1. Core recipe record
                recipe_stmt = """
                    SELECT r.id, r.source_dataset, r.source_id, r.title, r.description,
                           r.prep_time_minutes, r.cook_time_minutes, r.total_time_minutes,
                           r.servings, r.cuisine, r.source_url, r.submitted_date, r.created_at,
                           rr.rating_average, COALESCE(rr.rating_count, 0) AS rating_count,
                           rn.raw_calories, rn.raw_total_fat_pdv, rn.raw_sugar_pdv, rn.raw_sodium_pdv,
                           rn.raw_protein_pdv, rn.raw_saturated_fat_pdv, rn.raw_carbohydrates_pdv
                    FROM recipe_catalog.recipes r
                    LEFT JOIN recipe_catalog.recipe_ratings rr ON rr.recipe_id = r.id
                    LEFT JOIN recipe_catalog.recipe_nutrition_raw rn ON rn.recipe_id = r.id
                    WHERE r.id = %s;
                """
                cur.execute(recipe_stmt, (recipe_id,))
                r = cur.fetchone()
                if not r:
                    return None

                # 2. Ingredients
                ing_stmt = """
                    SELECT ri.position, ri.raw_text, ri.canonical_ingredient_id, ci.name,
                           ri.quantity, ri.unit
                    FROM recipe_catalog.recipe_ingredients ri
                    LEFT JOIN recipe_catalog.canonical_ingredients ci ON ci.id = ri.canonical_ingredient_id
                    WHERE ri.recipe_id = %s
                    ORDER BY ri.position ASC;
                """
                cur.execute(ing_stmt, (recipe_id,))
                ingredients: List[RecipeIngredientItem] = []
                for ing in cur.fetchall():
                    qty = float(ing[4]) if ing[4] is not None else None
                    ingredients.append(
                        RecipeIngredientItem(
                            position=int(ing[0]),
                            raw_text=ing[1],
                            canonical_ingredient_id=ing[2],
                            canonical_name=ing[3],
                            quantity=qty,
                            unit=ing[5],
                        )
                    )

                # 3. Instructions
                inst_stmt = """
                    SELECT step_number, instruction
                    FROM recipe_catalog.recipe_instructions
                    WHERE recipe_id = %s
                    ORDER BY step_number ASC;
                """
                cur.execute(inst_stmt, (recipe_id,))
                instructions: List[RecipeInstructionItem] = [
                    RecipeInstructionItem(step_number=int(step[0]), instruction=step[1])
                    for step in cur.fetchall()
                ]

                # 4. Tags
                tags_stmt = """
                    SELECT tag
                    FROM recipe_catalog.recipe_tags
                    WHERE recipe_id = %s
                    ORDER BY tag ASC;
                """
                cur.execute(tags_stmt, (recipe_id,))
                tags: List[str] = [t[0] for t in cur.fetchall()]

                # 5. Raw nutrition
                raw_nut: Optional[RecipeRawNutrition] = None
                if r[15] is not None:
                    raw_nut = RecipeRawNutrition(
                        raw_calories=float(r[15]),
                        raw_total_fat_pdv=float(r[16]) if r[16] is not None else None,
                        raw_sugar_pdv=float(r[17]) if r[17] is not None else None,
                        raw_sodium_pdv=float(r[18]) if r[18] is not None else None,
                        raw_protein_pdv=float(r[19]) if r[19] is not None else None,
                        raw_saturated_fat_pdv=float(r[20]) if r[20] is not None else None,
                        raw_carbohydrates_pdv=float(r[21]) if r[21] is not None else None,
                    )

                rating_avg = float(r[13]) if r[13] is not None else None

                return RecipeDetail(
                    id=r[0],
                    source_dataset=r[1],
                    source_id=r[2],
                    title=r[3],
                    description=r[4],
                    prep_time_minutes=r[5],
                    cook_time_minutes=r[6],
                    total_time_minutes=r[7],
                    servings=r[8],
                    cuisine=r[9],
                    source_url=r[10],
                    submitted_date=r[11],
                    created_at=r[12],
                    rating_average=rating_avg,
                    rating_count=int(r[14]),
                    ingredients=ingredients,
                    instructions=instructions,
                    tags=tags,
                    raw_nutrition=raw_nut,
                )

    def batch_get_recipes(
        self, recipe_ids: List[str], fields: Optional[List[str]] = None
    ) -> Tuple[List[RecipeDetail], List[str]]:
        """Retrieve up to 100 recipe details in a single batch operation without N+1 queries."""
        unique_ids = list(dict.fromkeys(recipe_ids))
        if not unique_ids:
            return [], []

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # 1. Fetch core records
                recipes_stmt = """
                    SELECT r.id, r.source_dataset, r.source_id, r.title, r.description,
                           r.prep_time_minutes, r.cook_time_minutes, r.total_time_minutes,
                           r.servings, r.cuisine, r.source_url, r.submitted_date, r.created_at,
                           rr.rating_average, COALESCE(rr.rating_count, 0) AS rating_count,
                           rn.raw_calories, rn.raw_total_fat_pdv, rn.raw_sugar_pdv, rn.raw_sodium_pdv,
                           rn.raw_protein_pdv, rn.raw_saturated_fat_pdv, rn.raw_carbohydrates_pdv
                    FROM recipe_catalog.recipes r
                    LEFT JOIN recipe_catalog.recipe_ratings rr ON rr.recipe_id = r.id
                    LEFT JOIN recipe_catalog.recipe_nutrition_raw rn ON rn.recipe_id = r.id
                    WHERE r.id = ANY(%s);
                """
                cur.execute(recipes_stmt, (unique_ids,))
                rows = cur.fetchall()
                found_map: Dict[str, Any] = {row[0]: row for row in rows}
                not_found = [rid for rid in unique_ids if rid not in found_map]
                found_ids = list(found_map.keys())

                if not found_ids:
                    return [], not_found

                # 2. Batch fetch ingredients
                ings_map: Dict[str, List[RecipeIngredientItem]] = {rid: [] for rid in found_ids}
                ing_stmt = """
                    SELECT ri.recipe_id, ri.position, ri.raw_text, ri.canonical_ingredient_id,
                           ci.name, ri.quantity, ri.unit
                    FROM recipe_catalog.recipe_ingredients ri
                    LEFT JOIN recipe_catalog.canonical_ingredients ci ON ci.id = ri.canonical_ingredient_id
                    WHERE ri.recipe_id = ANY(%s)
                    ORDER BY ri.recipe_id, ri.position ASC;
                """
                cur.execute(ing_stmt, (found_ids,))
                for ing in cur.fetchall():
                    rid = ing[0]
                    qty = float(ing[5]) if ing[5] is not None else None
                    ings_map[rid].append(
                        RecipeIngredientItem(
                            position=int(ing[1]),
                            raw_text=ing[2],
                            canonical_ingredient_id=ing[3],
                            canonical_name=ing[4],
                            quantity=qty,
                            unit=ing[6],
                        )
                    )

                # 3. Batch fetch instructions
                inst_map: Dict[str, List[RecipeInstructionItem]] = {rid: [] for rid in found_ids}
                inst_stmt = """
                    SELECT recipe_id, step_number, instruction
                    FROM recipe_catalog.recipe_instructions
                    WHERE recipe_id = ANY(%s)
                    ORDER BY recipe_id, step_number ASC;
                """
                cur.execute(inst_stmt, (found_ids,))
                for inst in cur.fetchall():
                    rid = inst[0]
                    inst_map[rid].append(
                        RecipeInstructionItem(step_number=int(inst[1]), instruction=inst[2])
                    )

                # 4. Batch fetch tags
                tags_map: Dict[str, List[str]] = {rid: [] for rid in found_ids}
                tags_stmt = """
                    SELECT recipe_id, tag
                    FROM recipe_catalog.recipe_tags
                    WHERE recipe_id = ANY(%s)
                    ORDER BY recipe_id, tag ASC;
                """
                cur.execute(tags_stmt, (found_ids,))
                for t in cur.fetchall():
                    tags_map[t[0]].append(t[1])

                # Assemble details in original requested order
                results: List[RecipeDetail] = []
                for rid in unique_ids:
                    if rid not in found_map:
                        continue
                    r = found_map[rid]
                    raw_nut: Optional[RecipeRawNutrition] = None
                    if r[15] is not None:
                        raw_nut = RecipeRawNutrition(
                            raw_calories=float(r[15]),
                            raw_total_fat_pdv=float(r[16]) if r[16] is not None else None,
                            raw_sugar_pdv=float(r[17]) if r[17] is not None else None,
                            raw_sodium_pdv=float(r[18]) if r[18] is not None else None,
                            raw_protein_pdv=float(r[19]) if r[19] is not None else None,
                            raw_saturated_fat_pdv=float(r[20]) if r[20] is not None else None,
                            raw_carbohydrates_pdv=float(r[21]) if r[21] is not None else None,
                        )

                    rating_avg = float(r[13]) if r[13] is not None else None

                    results.append(
                        RecipeDetail(
                            id=r[0],
                            source_dataset=r[1],
                            source_id=r[2],
                            title=r[3],
                            description=r[4],
                            prep_time_minutes=r[5],
                            cook_time_minutes=r[6],
                            total_time_minutes=r[7],
                            servings=r[8],
                            cuisine=r[9],
                            source_url=r[10],
                            submitted_date=r[11],
                            created_at=r[12],
                            rating_average=rating_avg,
                            rating_count=int(r[14]),
                            ingredients=ings_map.get(rid, []),
                            instructions=inst_map.get(rid, []),
                            tags=tags_map.get(rid, []),
                            raw_nutrition=raw_nut,
                        )
                    )

                return results, not_found

    def normalize_ingredients(self, raw_inputs: List[str]) -> List[NormalizedIngredientResult]:
        """Normalize free-form ingredient text against canonical dictionary and synonyms."""
        results: List[NormalizedIngredientResult] = []
        if not raw_inputs:
            return results

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                for text in raw_inputs:
                    trimmed = text.strip()
                    if not trimmed:
                        results.append(
                            NormalizedIngredientResult(
                                raw_input=text,
                                matched=False,
                                canonical_id=None,
                                canonical_name=None,
                                category=None,
                                is_pantry_staple=None,
                                confidence=None,
                            )
                        )
                        continue

                    # Safely identify and detach leading quantity/unit prefix before compound check
                    stripped = _strip_quantity_unit_prefix(trimmed)
                    check_target = stripped if stripped else trimmed
                    if _COMPOUND_PATTERN.search(check_target):
                        results.append(
                            NormalizedIngredientResult(
                                raw_input=text,
                                matched=False,
                                canonical_id=None,
                                canonical_name=None,
                                category=None,
                                is_pantry_staple=None,
                                confidence=None,
                            )
                        )
                        continue

                    # 1. Exact match in canonical_ingredients
                    cur.execute(
                        """
                        SELECT id, name, category, is_pantry_staple
                        FROM recipe_catalog.canonical_ingredients
                        WHERE LOWER(name) = LOWER(%s)
                        LIMIT 1;
                        """,
                        (trimmed,),
                    )
                    row = cur.fetchone()
                    if row:
                        results.append(
                            NormalizedIngredientResult(
                                raw_input=text,
                                matched=True,
                                canonical_id=row[0],
                                canonical_name=row[1],
                                category=row[2],
                                is_pantry_staple=row[3],
                                confidence=1.0,
                            )
                        )
                        continue

                    # 2. Exact match in ingredient_synonyms
                    cur.execute(
                        """
                        SELECT ci.id, ci.name, ci.category, ci.is_pantry_staple
                        FROM recipe_catalog.ingredient_synonyms s
                        JOIN recipe_catalog.canonical_ingredients ci ON ci.id = s.canonical_ingredient_id
                        WHERE LOWER(s.synonym) = LOWER(%s)
                        LIMIT 1;
                        """,
                        (trimmed,),
                    )
                    row = cur.fetchone()
                    if row:
                        results.append(
                            NormalizedIngredientResult(
                                raw_input=text,
                                matched=True,
                                canonical_id=row[0],
                                canonical_name=row[1],
                                category=row[2],
                                is_pantry_staple=row[3],
                                confidence=0.95,
                            )
                        )
                        continue

                    # 3. Strip quantity/unit prefix and match
                    if stripped and stripped != trimmed:
                        cur.execute(
                            """
                            SELECT id, name, category, is_pantry_staple
                            FROM recipe_catalog.canonical_ingredients
                            WHERE LOWER(name) = LOWER(%s)
                            LIMIT 1;
                            """,
                            (stripped,),
                        )
                        row = cur.fetchone()
                        if row:
                            results.append(
                                NormalizedIngredientResult(
                                    raw_input=text,
                                    matched=True,
                                    canonical_id=row[0],
                                    canonical_name=row[1],
                                    category=row[2],
                                    is_pantry_staple=row[3],
                                    confidence=0.95,
                                )
                            )
                            continue

                        cur.execute(
                            """
                            SELECT ci.id, ci.name, ci.category, ci.is_pantry_staple
                            FROM recipe_catalog.ingredient_synonyms s
                            JOIN recipe_catalog.canonical_ingredients ci ON ci.id = s.canonical_ingredient_id
                            WHERE LOWER(s.synonym) = LOWER(%s)
                            LIMIT 1;
                            """,
                            (stripped,),
                        )
                        row = cur.fetchone()
                        if row:
                            results.append(
                                NormalizedIngredientResult(
                                    raw_input=text,
                                    matched=True,
                                    canonical_id=row[0],
                                    canonical_name=row[1],
                                    category=row[2],
                                    is_pantry_staple=row[3],
                                    confidence=0.95,
                                )
                            )
                            continue

                    # No definitive match found in dictionary (fuzzy similarity is suggestion-only)
                    results.append(
                        NormalizedIngredientResult(
                            raw_input=text,
                            matched=False,
                            canonical_id=None,
                            canonical_name=None,
                            category=None,
                            is_pantry_staple=None,
                            confidence=None,
                        )
                    )

        return results

    def get_ingredient_suggestions(self, query: str, limit: int = 10) -> List[IngredientSuggestion]:
        """Autocomplete suggestions for canonical ingredients."""
        trimmed = query.strip()
        if not trimmed:
            return []

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, category, is_pantry_staple
                    FROM recipe_catalog.canonical_ingredients
                    WHERE name ILIKE %s OR similarity(name, %s) >= 0.2
                    ORDER BY similarity(name, %s) DESC, name ASC
                    LIMIT %s;
                    """,
                    (f"%{trimmed}%", trimmed, trimmed, limit),
                )
                return [
                    IngredientSuggestion(
                        id=row[0],
                        name=row[1],
                        category=row[2],
                        is_pantry_staple=bool(row[3]),
                    )
                    for row in cur.fetchall()
                ]

    def search_recipes_by_ingredients(
        self,
        canonical_ingredient_ids: List[int],
        exclude_pantry_staples: bool = True,
        min_match_pct: float = 20.0,
        page: int = 1,
        limit: int = 24,
    ) -> Tuple[List[IngredientCandidateItem], int]:
        """Find candidate recipes containing specified canonical ingredients with match scoring."""
        if not canonical_ingredient_ids:
            return [], 0

        offset = (page - 1) * limit

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                if exclude_pantry_staples:
                    tracked_filter = "FILTER (WHERE ci.name IS NULL OR LOWER(ci.name) NOT IN ('water', 'salt', 'black pepper', 'pepper'))"
                else:
                    tracked_filter = ""

                # Total count of candidate recipes meeting min_match_pct threshold
                count_stmt = f"""
                    WITH candidate_recipes AS (
                        SELECT ri.recipe_id
                        FROM recipe_catalog.recipe_ingredients ri
                        WHERE ri.canonical_ingredient_id = ANY(%s)
                        GROUP BY ri.recipe_id
                    ),
                    matched_recipes AS (
                        SELECT ri.recipe_id,
                               ARRAY_AGG(DISTINCT ri.canonical_ingredient_id)
                                   FILTER (WHERE ri.canonical_ingredient_id = ANY(%s)) AS matched_ids,
                               ARRAY_AGG(DISTINCT ri.canonical_ingredient_id)
                                   FILTER (WHERE ri.canonical_ingredient_id IS NOT NULL) AS all_ids,
                               COUNT(ri.id) AS total_ingredients,
                               COUNT(ri.id) {tracked_filter} AS tracked_ingredients
                        FROM recipe_catalog.recipe_ingredients ri
                        JOIN candidate_recipes cr ON cr.recipe_id = ri.recipe_id
                        LEFT JOIN recipe_catalog.canonical_ingredients ci ON ci.id = ri.canonical_ingredient_id
                        GROUP BY ri.recipe_id
                    )
                    SELECT COUNT(*)
                    FROM matched_recipes
                    WHERE (CARDINALITY(matched_ids)::numeric * 100.0 / NULLIF(tracked_ingredients, 0)) >= %s;
                """
                cur.execute(
                    count_stmt,
                    (canonical_ingredient_ids, canonical_ingredient_ids, min_match_pct),
                )
                row = cur.fetchone()
                total_items = row[0] if row else 0

                if total_items == 0:
                    return [], 0

                # Fetch page of candidate recipes
                data_stmt = f"""
                    WITH candidate_recipes AS (
                        SELECT ri.recipe_id
                        FROM recipe_catalog.recipe_ingredients ri
                        WHERE ri.canonical_ingredient_id = ANY(%s)
                        GROUP BY ri.recipe_id
                    ),
                    matched_recipes AS (
                        SELECT ri.recipe_id,
                               ARRAY_AGG(DISTINCT ri.canonical_ingredient_id)
                                   FILTER (WHERE ri.canonical_ingredient_id = ANY(%s)) AS matched_ids,
                               ARRAY_AGG(DISTINCT ri.canonical_ingredient_id)
                                   FILTER (WHERE ri.canonical_ingredient_id IS NOT NULL) AS all_ids,
                               COUNT(ri.id) AS total_ingredients,
                               COUNT(ri.id) {tracked_filter} AS tracked_ingredients
                        FROM recipe_catalog.recipe_ingredients ri
                        JOIN candidate_recipes cr ON cr.recipe_id = ri.recipe_id
                        LEFT JOIN recipe_catalog.canonical_ingredients ci ON ci.id = ri.canonical_ingredient_id
                        GROUP BY ri.recipe_id
                    )
                    SELECT mr.recipe_id, r.title, r.source_dataset, r.total_time_minutes, r.servings,
                           rr.rating_average, COALESCE(rr.rating_count, 0) AS rating_count,
                           mr.matched_ids, mr.all_ids, mr.total_ingredients,
                           ROUND((CARDINALITY(mr.matched_ids)::numeric * 100.0 / NULLIF(mr.tracked_ingredients, 0)), 1) AS match_pct
                    FROM matched_recipes mr
                    JOIN recipe_catalog.recipes r ON r.id = mr.recipe_id
                    LEFT JOIN recipe_catalog.recipe_ratings rr ON rr.recipe_id = r.id
                    WHERE (CARDINALITY(mr.matched_ids)::numeric * 100.0 / NULLIF(mr.tracked_ingredients, 0)) >= %s
                    ORDER BY match_pct DESC, r.id ASC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(
                    data_stmt,
                    (
                        canonical_ingredient_ids,
                        canonical_ingredient_ids,
                        min_match_pct,
                        limit,
                        offset,
                    ),
                )
                rows = cur.fetchall()

                candidates: List[IngredientCandidateItem] = []
                for row in rows:
                    rating_avg = float(row[5]) if row[5] is not None else None
                    candidates.append(
                        IngredientCandidateItem(
                            recipe_id=row[0],
                            title=row[1],
                            source_dataset=row[2],
                            total_time_minutes=row[3],
                            servings=row[4],
                            rating_average=rating_avg,
                            rating_count=int(row[6]),
                            matched_canonical_ids=list(row[7]) if row[7] else [],
                            recipe_canonical_ids=list(row[8]) if row[8] else [],
                            total_recipe_ingredients=int(row[9]),
                            match_pct=float(row[10]),
                        )
                    )

                return candidates, total_items

