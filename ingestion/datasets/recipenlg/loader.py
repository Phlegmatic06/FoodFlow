"""RecipeNLG PostgreSQL Database Loader

Executes transactional batch operations against the recipe_catalog schema
using psycopg 3 with full-text search vector generation (tsv_search),
conservative ingredient normalization, and idempotent child row synchronization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.datasets.recipenlg.parser import parse_ingredient_amount_and_unit
from ingestion.datasets.recipenlg.validator import ValidatedRecipeNLG
from ingestion.logging_config import get_logger


logger = get_logger("recipenlg.loader")


class RecipeNLGLoader:
    """Manages transactional batch persistence of RecipeNLG records into PostgreSQL 16."""

    def __init__(self, connection: Any):
        self.conn = connection

    def fetch_existing_recipenlg_recipe_ids(self) -> Set[str]:
        """Fetch all existing recipe IDs belonging to 'recipenlg' in recipe_catalog.recipes."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM recipe_catalog.recipes WHERE source_dataset = 'recipenlg';")
            return {row[0] for row in cur.fetchall()}

    def fetch_canonical_ingredient_map(self) -> Dict[str, int]:
        """Fetch canonical ingredients and synonyms mapping lowercase tokens to canonical IDs."""
        mapping: Dict[str, int] = {}
        with self.conn.cursor() as cur:
            # 1. Canonical ingredients
            cur.execute("SELECT id, name FROM recipe_catalog.canonical_ingredients;")
            for row in cur.fetchall():
                mapping[row[1].strip().lower()] = row[0]

            # 2. Ingredient synonyms
            cur.execute("SELECT synonym, canonical_ingredient_id FROM recipe_catalog.ingredient_synonyms;")
            for row in cur.fetchall():
                mapping[row[0].strip().lower()] = row[1]
        return mapping

    def check_source_origin_column_exists(self) -> bool:
        """Check whether the source_origin column exists on recipe_catalog.recipes."""
        sql = """
            SELECT 1 FROM information_schema.columns 
            WHERE table_schema = 'recipe_catalog' 
              AND table_name = 'recipes' 
              AND column_name = 'source_origin';
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchone() is not None
        except Exception as e:
            logger.warning(f"Error checking source_origin column existence: {e}")
            return False

    @staticmethod
    def match_canonical_ingredient(
        raw_text: str,
        ner_entities: Optional[List[str]],
        canon_map: Dict[str, int],
    ) -> Tuple[Optional[int], bool]:
        """Match an ingredient string to a canonical ingredient ID without ambiguous guessing.
        
        Returns:
            (canonical_id, is_ambiguous)
            - If exact or unambiguous single match: (id, False)
            - If conflicting/ambiguous matches: (None, True)
            - If no match found: (None, False)
        """
        if not canon_map:
            return None, False

        lower_raw = raw_text.strip().lower()

        # 1. Direct full string match against canonical dictionary
        if lower_raw in canon_map:
            return canon_map[lower_raw], False

        # 2. Match via pre-extracted NER food entities if available
        if ner_entities:
            matched_ids: Set[int] = set()
            for entity in ner_entities:
                norm_entity = entity.strip().lower()
                if norm_entity in canon_map and norm_entity in lower_raw:
                    matched_ids.add(canon_map[norm_entity])

            if len(matched_ids) == 1:
                return next(iter(matched_ids)), False
            elif len(matched_ids) > 1:
                # Ambiguous: multiple conflicting canonical ingredients detected in one raw line
                return None, True

        return None, False

    def load_recipes_batch(
        self,
        recipes: List[ValidatedRecipeNLG],
        canonical_map: Optional[Dict[str, int]] = None,
        has_source_origin: bool = True,
    ) -> Dict[str, int]:
        """Persist a batch of RecipeNLG recipes and child ingredients/instructions.
        
        Performs:
          - Upsert of recipe_catalog.recipes with search vector tsv_search.
          - Idempotent clearing of previous child records for the current batch IDs.
          - Batch insertion into recipe_ingredients with conservative quantity/unit parsing.
          - Batch insertion into recipe_instructions.
        """
        if not recipes:
            return {
                "recipes": 0,
                "recipe_ingredients": 0,
                "recipe_instructions": 0,
                "canonical_links": 0,
                "ambiguous_ingredients": 0,
            }

        canon_lookup = canonical_map or {}
        recipe_ids = [r.id for r in recipes]
        canonical_links_count = 0
        ambiguous_ingredients_count = 0

        with self.conn.cursor() as cur:
            # 1. Upsert recipes
            if has_source_origin:
                recipe_sql = """
                    INSERT INTO recipe_catalog.recipes (
                        id, source_dataset, source_id, title, description,
                        source_origin, source_url,
                        prep_time_minutes, cook_time_minutes, total_time_minutes,
                        servings, cuisine, submitted_date,
                        tsv_search
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        setweight(to_tsvector('english', COALESCE(%s, '')), 'A') ||
                        setweight(to_tsvector('english', COALESCE(%s, '')), 'B')
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        source_origin = EXCLUDED.source_origin,
                        source_url = EXCLUDED.source_url,
                        tsv_search = EXCLUDED.tsv_search;
                """
                recipe_params = [
                    (
                        r.id,
                        r.source_dataset,
                        r.source_id,
                        r.title,
                        None,  # description is NULL for RecipeNLG
                        r.source_origin,
                        r.source_url,
                        None,  # prep_time_minutes
                        None,  # cook_time_minutes
                        None,  # total_time_minutes
                        None,  # servings
                        None,  # cuisine
                        None,  # submitted_date
                        r.title,  # TSV Weight A
                        " ".join(r.ingredients),  # TSV Weight B (ingredient text)
                    )
                    for r in recipes
                ]
            else:
                recipe_sql = """
                    INSERT INTO recipe_catalog.recipes (
                        id, source_dataset, source_id, title, description,
                        source_url,
                        prep_time_minutes, cook_time_minutes, total_time_minutes,
                        servings, cuisine, submitted_date,
                        tsv_search
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        setweight(to_tsvector('english', COALESCE(%s, '')), 'A') ||
                        setweight(to_tsvector('english', COALESCE(%s, '')), 'B')
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        source_url = EXCLUDED.source_url,
                        tsv_search = EXCLUDED.tsv_search;
                """
                recipe_params = [
                    (
                        r.id,
                        r.source_dataset,
                        r.source_id,
                        r.title,
                        None,
                        r.source_url,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        r.title,
                        " ".join(r.ingredients),
                    )
                    for r in recipes
                ]

            cur.executemany(recipe_sql, recipe_params)

            # 2. Clear existing child records for this batch of recipes (Idempotency)
            cur.execute("DELETE FROM recipe_catalog.recipe_ingredients WHERE recipe_id = ANY(%s);", (recipe_ids,))
            cur.execute("DELETE FROM recipe_catalog.recipe_instructions WHERE recipe_id = ANY(%s);", (recipe_ids,))

            # 3. Batch insert recipe_ingredients
            ing_params = []
            for r in recipes:
                for pos, raw_ing in enumerate(r.ingredients, start=1):
                    qty, unit = parse_ingredient_amount_and_unit(raw_ing)
                    canon_id, is_ambiguous = self.match_canonical_ingredient(
                        raw_text=raw_ing,
                        ner_entities=r.ner_entities,
                        canon_map=canon_lookup,
                    )
                    if canon_id is not None:
                        canonical_links_count += 1
                    if is_ambiguous:
                        ambiguous_ingredients_count += 1

                    ing_params.append((r.id, pos, raw_ing, canon_id, qty, unit))

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

        return {
            "recipes": len(recipes),
            "recipe_ingredients": len(ing_params),
            "recipe_instructions": len(ins_params),
            "canonical_links": canonical_links_count,
            "ambiguous_ingredients": ambiguous_ingredients_count,
        }

    def record_provenance(
        self,
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
                'recipenlg', %s, NOW(), %s, %s, %s, %s, %s, %s, %s
            );
        """
        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    source_url,
                    f"RecipeNLG ({release_version})",
                    file_name,
                    sha256_checksum,
                    total_rows,
                    imported_rows,
                    rejected_rows,
                    notes,
                ),
            )

