"""USDA FoodData Central Database Loader

Executes batch inserts with idempotent ON CONFLICT clauses into profile_nutrition schema
using psycopg 3 and parameterized SQL.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.datasets.usda.validator import (
    ValidatedFood,
    ValidatedFoodNutrient,
    ValidatedFoodPortion,
    ValidatedNutrient,
)
from ingestion.logging_config import get_logger


logger = get_logger("usda.loader")


class USDALoader:
    """Manages transactional batch persistence of USDA records into PostgreSQL 16."""

    def __init__(self, connection: Any):
        self.conn = connection

    def fetch_existing_food_ids(self) -> Set[int]:
        """Fetch all existing fdc_id values currently present in profile_nutrition.usda_foods."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT fdc_id FROM profile_nutrition.usda_foods;")
            return {row[0] for row in cur.fetchall()}

    def fetch_existing_nutrient_ids(self) -> Set[int]:
        """Fetch all existing id values currently present in profile_nutrition.usda_nutrients."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM profile_nutrition.usda_nutrients;")
            return {row[0] for row in cur.fetchall()}

    def fetch_existing_nutrients_metadata(self) -> Dict[int, Tuple[str, str]]:
        """Fetch existing nutrient (name, unit_name) to detect definition conflicts."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, name, unit_name FROM profile_nutrition.usda_nutrients;")
            return {row[0]: (row[1], row[2]) for row in cur.fetchall()}

    def load_foods(self, foods: List[ValidatedFood]) -> int:
        """Batch insert/update USDA food items."""
        if not foods:
            return 0

        sql = """
            INSERT INTO profile_nutrition.usda_foods (
                fdc_id, data_type, description, food_category_id, publication_date
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (fdc_id) DO UPDATE SET
                data_type = EXCLUDED.data_type,
                description = EXCLUDED.description,
                food_category_id = COALESCE(EXCLUDED.food_category_id, profile_nutrition.usda_foods.food_category_id),
                publication_date = COALESCE(EXCLUDED.publication_date, profile_nutrition.usda_foods.publication_date);
        """
        params = [
            (f.fdc_id, f.data_type, f.description, f.food_category_id, f.publication_date)
            for f in foods
        ]
        with self.conn.cursor() as cur:
            cur.executemany(sql, params)
        return len(foods)

    def load_nutrients(self, nutrients: List[ValidatedNutrient]) -> int:
        """Batch insert USDA nutrients, preserving existing definitions on conflict."""
        if not nutrients:
            return 0

        # Check for conflicting nutrient definitions
        existing = self.fetch_existing_nutrients_metadata()
        for n in nutrients:
            if n.id in existing:
                ex_name, ex_unit = existing[n.id]
                if ex_name.lower() != n.name.lower() or ex_unit.lower() != n.unit_name.lower():
                    logger.warning(
                        f"Nutrient definition conflict for ID {n.id}: "
                        f"Existing: '{ex_name}' ({ex_unit}) vs Incoming: '{n.name}' ({n.unit_name}). "
                        f"Preserving existing definition."
                    )

        sql = """
            INSERT INTO profile_nutrition.usda_nutrients (
                id, name, unit_name, nutrient_nbr, rank
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """
        params = [
            (n.id, n.name, n.unit_name, n.nutrient_nbr, n.rank)
            for n in nutrients
        ]
        with self.conn.cursor() as cur:
            cur.executemany(sql, params)
        return len(nutrients)

    def load_food_nutrients(self, food_nutrients: List[ValidatedFoodNutrient]) -> int:
        """Batch insert/update food nutrient measurement records."""
        if not food_nutrients:
            return 0

        sql = """
            INSERT INTO profile_nutrition.usda_food_nutrients (
                id, fdc_id, nutrient_id, amount, data_points, derivation_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                amount = EXCLUDED.amount,
                data_points = EXCLUDED.data_points,
                derivation_id = EXCLUDED.derivation_id;
        """
        params = [
            (fn.id, fn.fdc_id, fn.nutrient_id, fn.amount, fn.data_points, fn.derivation_id)
            for fn in food_nutrients
        ]
        with self.conn.cursor() as cur:
            cur.executemany(sql, params)
        return len(food_nutrients)

    def load_food_portions(self, portions: List[ValidatedFoodPortion]) -> int:
        """Batch insert/update household food portion conversions."""
        if not portions:
            return 0

        sql = """
            INSERT INTO profile_nutrition.usda_food_portions (
                id, fdc_id, seq_num, amount, measure_unit_id, portion_description, modifier, gram_weight
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                seq_num = EXCLUDED.seq_num,
                amount = EXCLUDED.amount,
                measure_unit_id = EXCLUDED.measure_unit_id,
                portion_description = EXCLUDED.portion_description,
                modifier = EXCLUDED.modifier,
                gram_weight = EXCLUDED.gram_weight;
        """
        params = [
            (
                p.id,
                p.fdc_id,
                p.seq_num,
                p.amount,
                p.measure_unit_id,
                p.portion_description,
                p.modifier,
                p.gram_weight,
            )
            for p in portions
        ]
        with self.conn.cursor() as cur:
            cur.executemany(sql, params)
        return len(portions)

    def record_provenance(
        self,
        collection_name: str,
        source_url: str,
        release_date: str,
        file_name: str,
        sha256_checksum: str,
        total_rows: int,
        imported_rows: int,
        rejected_rows: int,
        notes: Optional[str] = None,
    ) -> None:
        """Insert an audit log entry in profile_nutrition.ingestion_provenance."""
        sql = """
            INSERT INTO profile_nutrition.ingestion_provenance (
                source_dataset, source_url, download_timestamp, dataset_version,
                file_name, file_sha256_checksum, original_raw_row_count,
                imported_row_count, skipped_malformed_count, notes
            ) VALUES (
                'usda_fdc', %s, NOW(), %s, %s, %s, %s, %s, %s, %s
            );
        """
        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    source_url,
                    f"{collection_name} ({release_date})",
                    file_name,
                    sha256_checksum,
                    total_rows,
                    imported_rows,
                    rejected_rows,
                    notes,
                ),
            )

