"""Database repository layer for Profile & Nutrition Service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import psycopg
from psycopg import sql

from services.common.database import ServiceDatabaseManager
from services.profile_nutrition.schemas import (
    CachedRecipeNutrition,
    USDAFoodDetail,
    USDAFoodPortion,
    USDAFoodSummary,
    USDANutrientMeasurement,
)


class ProfileRepository:
    """Repository handling SQL queries for USDA FoodData Central and nutrition estimations."""

    def __init__(self, db_manager: ServiceDatabaseManager) -> None:
        self.db = db_manager

    def search_usda_foods(
        self,
        q: str,
        data_type: Optional[str] = None,
        page: int = 1,
        limit: int = 24,
    ) -> Tuple[List[USDAFoodSummary], int]:
        """Search USDA foods by description prefix/keyword with pagination."""
        clean_q = q.strip()
        where_clauses = ["description ILIKE %s"]
        params: List[Any] = [f"%{clean_q}%"]

        if data_type:
            where_clauses.append("data_type = %s")
            params.append(data_type)

        where_sql = "WHERE " + " AND ".join(where_clauses)
        offset = (page - 1) * limit

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # 1. Total count
                count_query = f"SELECT count(*) FROM profile_nutrition.usda_foods {where_sql};"
                cur.execute(count_query, params)
                row = cur.fetchone()
                total_items = row[0] if row else 0

                if total_items == 0:
                    return [], 0

                # 2. Paginated items
                data_query = f"""
                    SELECT fdc_id, data_type, description, food_category_id, publication_date
                    FROM profile_nutrition.usda_foods
                    {where_sql}
                    ORDER BY description ASC, fdc_id ASC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(data_query, params + [limit, offset])
                rows = cur.fetchall()

                foods: List[USDAFoodSummary] = [
                    USDAFoodSummary(
                        fdc_id=r[0],
                        data_type=r[1],
                        description=r[2],
                        food_category_id=r[3],
                        publication_date=r[4],
                    )
                    for r in rows
                ]

                return foods, total_items

    def get_usda_food_detail(self, fdc_id: int) -> Optional[USDAFoodDetail]:
        """Retrieve complete USDA food profile including nutrients per 100g and portions."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # 1. Food record
                cur.execute(
                    """
                    SELECT fdc_id, data_type, description, food_category_id, publication_date
                    FROM profile_nutrition.usda_foods
                    WHERE fdc_id = %s;
                    """,
                    (fdc_id,),
                )
                food = cur.fetchone()
                if not food:
                    return None

                # 2. Nutrient measurements
                cur.execute(
                    """
                    SELECT fn.nutrient_id, un.name, un.unit_name, fn.amount, fn.data_points
                    FROM profile_nutrition.usda_food_nutrients fn
                    JOIN profile_nutrition.usda_nutrients un ON un.id = fn.nutrient_id
                    WHERE fn.fdc_id = %s
                    ORDER BY fn.nutrient_id ASC;
                    """,
                    (fdc_id,),
                )
                nutrients: List[USDANutrientMeasurement] = [
                    USDANutrientMeasurement(
                        nutrient_id=r[0],
                        name=r[1],
                        unit_name=r[2],
                        amount_per_100g=float(r[3]) if r[3] is not None else None,
                        data_points=r[4],
                    )
                    for r in cur.fetchall()
                ]

                # 3. Portions
                cur.execute(
                    """
                    SELECT id, seq_num, amount, portion_description, modifier, gram_weight
                    FROM profile_nutrition.usda_food_portions
                    WHERE fdc_id = %s
                    ORDER BY seq_num ASC NULLS LAST, id ASC;
                    """,
                    (fdc_id,),
                )
                portions: List[USDAFoodPortion] = [
                    USDAFoodPortion(
                        id=r[0],
                        seq_num=r[1],
                        amount=float(r[2]) if r[2] is not None else None,
                        portion_description=r[3],
                        modifier=r[4],
                        gram_weight=float(r[5]),
                    )
                    for r in cur.fetchall()
                ]

                return USDAFoodDetail(
                    fdc_id=food[0],
                    data_type=food[1],
                    description=food[2],
                    food_category_id=food[3],
                    publication_date=food[4],
                    nutrients=nutrients,
                    portions=portions,
                )

    def get_cached_recipe_nutrition(self, recipe_id: str) -> Optional[CachedRecipeNutrition]:
        """Fetch cached recipe nutrition estimation from profile_nutrition.nutrition_estimates."""
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT recipe_id, status, calories_kcal, total_fat_g, saturated_fat_g,
                           carbohydrates_g, sugar_g, protein_g, sodium_mg, fiber_g,
                           ingredient_coverage_pct, mapped_ingredient_count, total_ingredient_count,
                           servings, provenance_note, calculated_at, updated_at
                    FROM profile_nutrition.nutrition_estimates
                    WHERE recipe_id = %s;
                    """,
                    (recipe_id,),
                )
                r = cur.fetchone()
                if not r:
                    return None

                return CachedRecipeNutrition(
                    recipe_id=r[0],
                    status=r[1],
                    calories_kcal=float(r[2]) if r[2] is not None else None,
                    total_fat_g=float(r[3]) if r[3] is not None else None,
                    saturated_fat_g=float(r[4]) if r[4] is not None else None,
                    carbohydrates_g=float(r[5]) if r[5] is not None else None,
                    sugar_g=float(r[6]) if r[6] is not None else None,
                    protein_g=float(r[7]) if r[7] is not None else None,
                    sodium_mg=float(r[8]) if r[8] is not None else None,
                    fiber_g=float(r[9]) if r[9] is not None else None,
                    ingredient_coverage_pct=float(r[10]) if r[10] is not None else None,
                    mapped_ingredient_count=r[11],
                    total_ingredient_count=r[12],
                    servings=r[13],
                    provenance_note=r[14],
                    calculated_at=r[15],
                    updated_at=r[16],
                )

    def save_recipe_nutrition(self, record: CachedRecipeNutrition) -> None:
        """Upsert a recipe nutrition calculation estimate into nutrition_estimates."""
        stmt = """
            INSERT INTO profile_nutrition.nutrition_estimates (
                recipe_id, status, calories_kcal, total_fat_g, saturated_fat_g,
                carbohydrates_g, sugar_g, protein_g, sodium_mg, fiber_g,
                ingredient_coverage_pct, mapped_ingredient_count, total_ingredient_count,
                servings, provenance_note, calculated_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            ON CONFLICT (recipe_id) DO UPDATE SET
                status = EXCLUDED.status,
                calories_kcal = EXCLUDED.calories_kcal,
                total_fat_g = EXCLUDED.total_fat_g,
                saturated_fat_g = EXCLUDED.saturated_fat_g,
                carbohydrates_g = EXCLUDED.carbohydrates_g,
                sugar_g = EXCLUDED.sugar_g,
                protein_g = EXCLUDED.protein_g,
                sodium_mg = EXCLUDED.sodium_mg,
                fiber_g = EXCLUDED.fiber_g,
                ingredient_coverage_pct = EXCLUDED.ingredient_coverage_pct,
                mapped_ingredient_count = EXCLUDED.mapped_ingredient_count,
                total_ingredient_count = EXCLUDED.total_ingredient_count,
                servings = EXCLUDED.servings,
                provenance_note = EXCLUDED.provenance_note,
                updated_at = NOW();
        """
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    stmt,
                    (
                        record.recipe_id,
                        record.status,
                        record.calories_kcal,
                        record.total_fat_g,
                        record.saturated_fat_g,
                        record.carbohydrates_g,
                        record.sugar_g,
                        record.protein_g,
                        record.sodium_mg,
                        record.fiber_g,
                        record.ingredient_coverage_pct,
                        record.mapped_ingredient_count,
                        record.total_ingredient_count,
                        record.servings,
                        record.provenance_note,
                    ),
                )
            conn.commit()

    def batch_get_nutrients(
        self, fdc_ids: List[int], nutrient_ids: List[int]
    ) -> Dict[int, Dict[int, float]]:
        """Batch retrieve nutrient amounts (per 100g) for multiple FDC IDs."""
        if not fdc_ids or not nutrient_ids:
            return {}

        results: Dict[int, Dict[int, float]] = {fid: {} for fid in fdc_ids}
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT fdc_id, nutrient_id, amount
                    FROM profile_nutrition.usda_food_nutrients
                    WHERE fdc_id = ANY(%s) AND nutrient_id = ANY(%s) AND amount IS NOT NULL;
                    """,
                    (fdc_ids, nutrient_ids),
                )
                for fdc_id, nut_id, amt in cur.fetchall():
                    if amt is not None:
                        results[fdc_id][nut_id] = float(amt)

        return results

    def batch_get_portions(self, fdc_ids: List[int]) -> Dict[int, List[USDAFoodPortion]]:
        """Batch retrieve household portion measures for multiple FDC IDs."""
        if not fdc_ids:
            return {}

        results: Dict[int, List[USDAFoodPortion]] = {fid: [] for fid in fdc_ids}
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, fdc_id, seq_num, amount, portion_description, modifier, gram_weight
                    FROM profile_nutrition.usda_food_portions
                    WHERE fdc_id = ANY(%s)
                    ORDER BY seq_num ASC NULLS LAST, id ASC;
                    """,
                    (fdc_ids,),
                )
                for r in cur.fetchall():
                    results[r[1]].append(
                        USDAFoodPortion(
                            id=r[0],
                            seq_num=r[2],
                            amount=float(r[3]) if r[3] is not None else None,
                            portion_description=r[4],
                            modifier=r[5],
                            gram_weight=float(r[6]),
                        )
                    )

        return results

    def find_fdc_id_by_name(self, term: str) -> Optional[int]:
        """Find authoritative FDC ID by exact lexical match on description."""
        clean = term.strip()
        if not clean:
            return None

        with self.db.connection() as conn:
            with conn.cursor() as cur:
                # Exact match on description (case-insensitive)
                cur.execute(
                    """
                    SELECT fdc_id FROM profile_nutrition.usda_foods
                    WHERE LOWER(description) = LOWER(%s)
                    LIMIT 1;
                    """,
                    (clean,),
                )
                row = cur.fetchone()
                if row:
                    return row[0]

                return None

