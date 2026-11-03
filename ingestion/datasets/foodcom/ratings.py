"""Food.com Ratings Aggregator

Implements bounded-memory streaming aggregation of historical ratings from
RAW_interactions.csv into recipe_catalog.recipe_ratings.

Uses a temporary PostgreSQL staging table to accumulate exact rating sums and counts
across streaming batches, preventing rounded average drift while keeping Python
memory overhead strictly O(batch_size).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

from ingestion.datasets.foodcom.validator import (
    FoodComValidationError,
    UnmatchedRecipeError,
    validate_interaction_record,
)
from ingestion.logging_config import get_logger


logger = get_logger("foodcom.ratings")


@dataclass
class RatingsAggregationMetrics:
    total_rows: int = 0
    valid_ratings: int = 0
    invalid_ratings: int = 0
    unmatched_ratings: int = 0
    updated_recipes_count: int = 0


class RatingsAggregator:
    """Aggregates Food.com review star ratings with streaming memory bounds."""

    def __init__(self, connection: Optional[Any] = None, batch_size: int = 5000):
        self.conn = connection
        self.batch_size = max(100, batch_size)

    def create_staging_table(self) -> None:
        """Create a session-scoped temporary table for aggregating rating sums and counts."""
        if not self.conn:
            return
        sql = """
            CREATE TEMP TABLE IF NOT EXISTS temp_foodcom_ratings_staging (
                recipe_id VARCHAR(64) PRIMARY KEY,
                rating_sum NUMERIC(14, 2) NOT NULL DEFAULT 0,
                rating_count INTEGER NOT NULL DEFAULT 0
            );
            TRUNCATE TABLE temp_foodcom_ratings_staging;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)

    def drop_staging_table(self) -> None:
        """Cleanly drop the temporary staging table."""
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS temp_foodcom_ratings_staging;")
        except Exception as e:
            logger.warning(f"Error dropping temporary ratings staging table: {e}")

    def stage_batch(self, batch_aggregates: Dict[str, List[float]]) -> None:
        """Upsert a single batch's rating aggregates into the temporary staging table.
        
        batch_aggregates: {recipe_id: [batch_sum, batch_count]}
        """
        if not self.conn or not batch_aggregates:
            return

        sql = """
            INSERT INTO temp_foodcom_ratings_staging (recipe_id, rating_sum, rating_count)
            VALUES (%s, %s, %s)
            ON CONFLICT (recipe_id) DO UPDATE SET
                rating_sum = temp_foodcom_ratings_staging.rating_sum + EXCLUDED.rating_sum,
                rating_count = temp_foodcom_ratings_staging.rating_count + EXCLUDED.rating_count;
        """
        params = [
            (recipe_id, vals[0], int(vals[1]))
            for recipe_id, vals in batch_aggregates.items()
        ]
        with self.conn.cursor() as cur:
            cur.executemany(sql, params)

    def commit_staging_to_ratings_table(self) -> int:
        """Transfer aggregated ratings from temp staging table into recipe_catalog.recipe_ratings.
        
        Guarantees that only recipes belonging to 'food_com' in the catalogue are updated.
        Calculates exact mathematical average ROUND(rating_sum / rating_count, 2).
        """
        if not self.conn:
            return 0

        sql = """
            INSERT INTO recipe_catalog.recipe_ratings (
                recipe_id, rating_average, rating_count, updated_at
            )
            SELECT 
                s.recipe_id,
                ROUND((s.rating_sum / s.rating_count)::numeric, 2) AS rating_average,
                s.rating_count,
                NOW() AS updated_at
            FROM temp_foodcom_ratings_staging s
            JOIN recipe_catalog.recipes r ON r.id = s.recipe_id
            WHERE s.rating_count > 0 AND r.source_dataset = 'food_com'
            ON CONFLICT (recipe_id) DO UPDATE SET
                rating_average = EXCLUDED.rating_average,
                rating_count = EXCLUDED.rating_count,
                updated_at = NOW();
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.rowcount

    def process_interactions_stream(
        self,
        interactions_stream: Generator[Tuple[int, Dict[str, str]], None, None],
        known_recipe_ids: Optional[Set[str]] = None,
        dry_run: bool = False,
        limit: Optional[int] = None,
    ) -> RatingsAggregationMetrics:
        """Stream RAW_interactions.csv, validating and aggregating ratings.
        
        In live mode: updates PostgreSQL staging table incrementally.
        In dry-run mode: validates and tallies metrics in-memory without DB queries.
        """
        metrics = RatingsAggregationMetrics()
        batch_acc: Dict[str, List[float]] = {}  # {recipe_id: [sum, count]}
        distinct_dry_run_recipes: Set[str] = set()

        if not dry_run and self.conn:
            self.create_staging_table()

        try:
            for line_num, row in interactions_stream:
                if limit and metrics.total_rows >= limit:
                    break
                metrics.total_rows += 1

                try:
                    inter = validate_interaction_record(
                        row=row,
                        line_number=line_num,
                        known_recipe_ids=known_recipe_ids,
                    )
                    metrics.valid_ratings += 1

                    if dry_run:
                        distinct_dry_run_recipes.add(inter.recipe_id)
                    else:
                        # Accumulate in current batch
                        if inter.recipe_id not in batch_acc:
                            batch_acc[inter.recipe_id] = [0.0, 0]
                        batch_acc[inter.recipe_id][0] += inter.rating
                        batch_acc[inter.recipe_id][1] += 1

                        if len(batch_acc) >= self.batch_size:
                            self.stage_batch(batch_acc)
                            batch_acc = {}

                except UnmatchedRecipeError:
                    metrics.unmatched_ratings += 1
                except FoodComValidationError:
                    metrics.invalid_ratings += 1

            # Flush final batch
            if not dry_run and batch_acc:
                self.stage_batch(batch_acc)
                batch_acc = {}

            # Finalize to permanent table
            if not dry_run and self.conn:
                metrics.updated_recipes_count = self.commit_staging_to_ratings_table()
            else:
                metrics.updated_recipes_count = len(distinct_dry_run_recipes)

            return metrics

        finally:
            if not dry_run and self.conn:
                self.drop_staging_table()

