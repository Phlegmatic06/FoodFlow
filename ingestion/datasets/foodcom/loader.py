"""Food.com PostgreSQL Database Loader

Executes transactional batch operations against the recipe_catalog schema
using psycopg 3 with full-text search vector generation (tsv_search)
and idempotent child row synchronization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.datasets.foodcom.validator import ValidatedRecipe
from ingestion.logging_config import get_logger


logger = get_logger("foodcom.loader")


class FoodComLoader:
    """Manages transactional batch persistence of Food.com records into PostgreSQL 16."""

    def __init__(self, connection: Any):
        self.conn = connection

    def fetch_existing_foodcom_recipe_ids(self) -> Set[str]:
        """Fetch all existing recipe IDs belonging to 'food_com' in recipe_catalog.recipes."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM recipe_catalog.recipes WHERE source_dataset = 'food_com';")
            return {row[0] for row in cur.fetchall()}

    def fetch_canonical_ingredient_map(self) -> Dict[str, int]:
        """Fetch canonical ingredients and synonyms mapping lowercase tokens to canonical IDs."""
        mapping: Dict[str, int] = {}
        with self.conn.cursor() as cur:
            # 1. Direct canonical ingredients
            cur.execute("SELECT id, name FROM recipe_catalog.canonical_ingredients;")
            for row in cur.fetchall():
                mapping[row[1].strip().lower()] = row[0]

            # 2. Ingredient synonyms
            cur.execute("SELECT synonym, canonical_ingredient_id FROM recipe_catalog.ingredient_synonyms;")
            for row in cur.fetchall():
                mapping[row[0].strip().lower()] = row[1]
        return mapping

    def load_recipes_batch(
        self,
        recipes: List[ValidatedRecipe],
        canonical_map: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        """Persist a batch of recipes, child ingredients, instructions, tags, and raw nutrition.
        
        Uses an explicit sub-transaction. Synchronizes child rows idempotently by
        clearing previous child entries for the specific batch IDs before re-inserting.
        """
        if not recipes:
            return {
                "recipes": 0,
                "recipe_ingredients": 0,
                "recipe_instructions": 0,
                "recipe_tags": 0,
                "recipe_nutrition_raw": 0,
            }

        canon_lookup = canonical_map or {}
        recipe_ids = [r.id for r in recipes]

        with self.conn.cursor() as cur:
            # 1. Upsert recipes
            recipe_sql = """
                INSERT INTO recipe_catalog.recipes (
                    id, source_dataset, source_id, title, description,
                    prep_time_minutes, cook_time_minutes, total_time_minutes,
                    servings, cuisine, source_url, submitted_date,
                    tsv_search
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    setweight(to_tsvector('english', COALESCE(%s, '')), 'A') ||
                    setweight(to_tsvector('english', COALESCE(%s, '')), 'B') ||
                    setweight(to_tsvector('english', COALESCE(%s, '')), 'C')
                )
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    total_time_minutes = EXCLUDED.total_time_minutes,
                    source_url = EXCLUDED.source_url,
                    submitted_date = EXCLUDED.submitted_date,
                    tsv_search = EXCLUDED.tsv_search;
            """
            recipe_params = [
                (
                    r.id,
                    r.source_dataset,
                    r.source_id,
                    r.title,
                    r.description,
                    r.prep_time_minutes,
                    r.cook_time_minutes,
                    r.total_time_minutes,
                    r.servings,
                    r.cuisine,
                    r.source_url,
                    r.submitted_date,
                    # TSV vector inputs: title (Weight A), description (Weight B), tags (Weight C)
                    r.title,
                    r.description or "",
                    " ".join(r.tags),
                )
                for r in recipes
            ]
            cur.executemany(recipe_sql, recipe_params)

            # 2. Clear existing child records for this batch of recipes (Idempotency)
            cur.execute("DELETE FROM recipe_catalog.recipe_ingredients WHERE recipe_id = ANY(%s);", (recipe_ids,))
            cur.execute("DELETE FROM recipe_catalog.recipe_instructions WHERE recipe_id = ANY(%s);", (recipe_ids,))
            cur.execute("DELETE FROM recipe_catalog.recipe_tags WHERE recipe_id = ANY(%s);", (recipe_ids,))

            # 3. Batch insert recipe_ingredients
            ing_params = []
            for r in recipes:
                for pos, raw_ing in enumerate(r.ingredients, start=1):
                    # Check canonical match via taxonomy dictionary
                    canonical_id = canon_lookup.get(raw_ing.lower())
                    ing_params.append((r.id, pos, raw_ing, canonical_id, None, None))

            if ing_params:
                ing_sql = """
                    INSERT INTO recipe_catalog.recipe_ingredients (
                        recipe_id, position, raw_text, canonical_ingredient_id, quantity, unit
                    ) VALUES (%s, %s, %s, %s, %s, %s);
                """
                cur.executemany(ing_sql, ing_params)

            # 4. Batch insert recipe_instructions
            ins_params = []
            for r in recipes:
                for step_num, step_text in enumerate(r.instructions, start=1):
                    ins_params.append((r.id, step_num, step_text))

            if ins_params:
                ins_sql = """
                    INSERT INTO recipe_catalog.recipe_instructions (
                        recipe_id, step_number, instruction
                    ) VALUES (%s, %s, %s);
                """
                cur.executemany(ins_sql, ins_params)

            # 5. Batch insert recipe_tags
            tag_params = []
            for r in recipes:
                for tag in r.tags:
                    tag_params.append((r.id, tag))

            if tag_params:
                tag_sql = """
                    INSERT INTO recipe_catalog.recipe_tags (
                        recipe_id, tag
                    ) VALUES (%s, %s);
                """
                cur.executemany(tag_sql, tag_params)

            # 6. Upsert recipe_nutrition_raw
            nut_sql = """
                INSERT INTO recipe_catalog.recipe_nutrition_raw (
                    recipe_id, raw_calories, raw_total_fat_pdv, raw_sugar_pdv,
                    raw_sodium_pdv, raw_protein_pdv, raw_saturated_fat_pdv, raw_carbohydrates_pdv
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (recipe_id) DO UPDATE SET
                    raw_calories = EXCLUDED.raw_calories,
                    raw_total_fat_pdv = EXCLUDED.raw_total_fat_pdv,
                    raw_sugar_pdv = EXCLUDED.raw_sugar_pdv,
                    raw_sodium_pdv = EXCLUDED.raw_sodium_pdv,
                    raw_protein_pdv = EXCLUDED.raw_protein_pdv,
                    raw_saturated_fat_pdv = EXCLUDED.raw_saturated_fat_pdv,
                    raw_carbohydrates_pdv = EXCLUDED.raw_carbohydrates_pdv;
            """
            nut_params = [
                (
                    r.id,
                    r.nutrition[0],
                    r.nutrition[1],
                    r.nutrition[2],
                    r.nutrition[3],
                    r.nutrition[4],
                    r.nutrition[5],
                    r.nutrition[6],
                )
                for r in recipes
            ]
            cur.executemany(nut_sql, nut_params)

        return {
            "recipes": len(recipes),
            "recipe_ingredients": len(ing_params),
            "recipe_instructions": len(ins_params),
            "recipe_tags": len(tag_params),
            "recipe_nutrition_raw": len(nut_params),
        }

    def record_provenance(
        self,
        component_name: str,
        source_url: str,
        release_version: str,
        file_name: str,
        sha256_checksum: str,
        total_rows: int,
        imported_rows: int,
        rejected_rows: int,
        notes: Optional[str] = None,
    ) -> None:
        """Insert an audit log entry into recipe_catalog.ingestion_provenance."""
        sql = """
            INSERT INTO recipe_catalog.ingestion_provenance (
                source_dataset, source_url, download_timestamp, dataset_version,
                file_name, file_sha256_checksum, original_raw_row_count,
                imported_row_count, skipped_malformed_count, notes
            ) VALUES (
                'food_com', %s, NOW(), %s, %s, %s, %s, %s, %s, %s
            );
        """
        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    source_url,
                    f"Food.com {component_name} ({release_version})",
                    file_name,
                    sha256_checksum,
                    total_rows,
                    imported_rows,
                    rejected_rows,
                    notes,
                ),
            )

