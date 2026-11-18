"""NutriPod Unified Sampling Engine - Food.com Stratified Sampler

Implements reproducible, stratified reservoir sampling for Food.com recipes and
deterministic referential interaction filtering.

Stratification taxonomy:
  - Primary Category (Precedence: Breakfast -> Lunch -> Dinner -> Dessert -> Snack -> Beverage -> Other)
  - Cooking Time Bucket (<=15 min, 16-30 min, 31-60 min, >60 min, Unknown/invalid)
"""

from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.config import FOODCOM_RAW_DIR, PROCESSED_DATA_DIR
from ingestion.datasets.foodcom.parser import (
    FoodComParseError,
    FoodComSource,
    parse_time_minutes,
    safe_parse_python_list,
)
from ingestion.datasets.foodcom.validator import (
    FoodComValidationError,
    validate_headers,
    validate_recipe_record,
)
from ingestion.logging_config import get_logger
from ingestion.sampling.base import (
    StratifiedReservoirSampler,
    allocate_proportional_quotas,
)
from ingestion.sampling.reports import OutputFileMetadata, SamplingReport
from ingestion.utils.checksums import compute_file_sha256
from ingestion.utils.csv_utils import IngestionProgressTracker, configure_csv_limits


configure_csv_limits()
logger = get_logger("sampling.foodcom")

# Explicit known Food.com tags taxonomy
CATEGORY_TAG_MAP: Dict[str, Set[str]] = {
    "breakfast": {
        "breakfast", "brunch", "pancakes", "waffles", "cereal",
        "omelets-and-frittatas", "french-toast", "breakfast-casseroles",
        "crepes", "muffins", "eggs-breakfast", "scrambled-eggs",
    },
    "lunch": {
        "lunch", "sandwiches", "wraps", "salads", "salads-main-dish",
        "soups-stews", "chili", "soup", "lunchbox", "cold-lunches",
        "panini", "quiche",
    },
    "dinner": {
        "dinner", "main-dish", "entrees", "steaks", "pasta",
        "casseroles", "poultry", "meat", "beef", "chicken",
        "pork", "seafood", "fish", "roast", "stews", "one-dish-meal",
        "roast-beef", "curries", "pizzas", "ribs",
    },
    "dessert": {
        "desserts", "baking", "cookies-brownies", "cakes", "pies",
        "pies-and-tarts", "tarts", "cupcakes", "cheesecake",
        "puddings-mousses", "candy", "fudge", "pastry", "icing-frosting",
        "breads", "yeast-breads", "sweet-breads", "cobblers",
        "frozen-desserts", "ice-cream",
    },
    "snack": {
        "appetizers", "snacks", "finger-food", "dips-spreads",
        "canapes", "wings", "nachos", "chips", "popcorn",
        "snack-mixes", "nuts-seeds",
    },
    "beverage": {
        "beverages", "drinks", "smoothies", "cocktails",
        "coffee-tea", "tea", "coffee", "punch", "shakes-floats",
        "lemonade", "cider", "mocktails", "hot-chocolate",
    },
}

# Deterministic category precedence order for primary stratum assignment
CATEGORY_PRECEDENCE: List[str] = [
    "breakfast",
    "lunch",
    "dinner",
    "dessert",
    "snack",
    "beverage",
    "other",
]


def classify_foodcom_category(tags: Sequence[str]) -> str:
    """Classify recipe into a single primary category based on explicit tag matching.
    
    If multiple categories match, the first in CATEGORY_PRECEDENCE is selected.
    If no known tags match, returns 'other'.
    """
    if not tags:
        return "other"

    normalized_tags = {str(t).lower().strip() for t in tags}

    for category in CATEGORY_PRECEDENCE:
        if category == "other":
            continue
        known_tags = CATEGORY_TAG_MAP[category]
        if normalized_tags & known_tags:
            return category

    return "other"


def classify_cooking_time_bucket(minutes: Optional[int]) -> str:
    """Assign recipe to a discrete cooking time stratum bucket."""
    if minutes is None or minutes <= 0:
        return "time_unknown"
    if minutes <= 15:
        return "time_lte_15"
    if minutes <= 30:
        return "time_16_30"
    if minutes <= 60:
        return "time_31_60"
    return "time_gt_60"


def determine_foodcom_stratum(row: Dict[str, str], line_number: int = 1) -> str:
    """Compute the composite sampling stratum ID for a Food.com recipe row.
    
    Composite format: '{category}__{time_bucket}'
    """
    raw_tags = row.get("tags")
    parsed_tags: List[str] = []
    if raw_tags:
        try:
            parsed_tags = safe_parse_python_list(raw_tags, "tags", line_number)
        except FoodComParseError:
            parsed_tags = []

    category = classify_foodcom_category(parsed_tags)

    raw_minutes = row.get("minutes")
    minutes = parse_time_minutes(raw_minutes, line_number)
    time_bucket = classify_cooking_time_bucket(minutes)

    return f"{category}__{time_bucket}"


class FoodComSampler:
    """Orchestrates memory-bounded stratified sampling for Food.com."""

    def __init__(
        self,
        source_path: Path,
        output_dir: Optional[Path] = None,
        limit: int = 25000,
        seed: int = 42,
    ):
        self.source_path = Path(source_path).resolve()
        self.source = FoodComSource(self.source_path)
        self.limit = max(0, limit)
        self.seed = seed

        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            self.output_dir = (PROCESSED_DATA_DIR / "dev_sample" / "foodcom").resolve()

    def run(self, dry_run: bool = False) -> SamplingReport:
        """Execute the two-pass stratified sampling and interaction filtering workflow."""
        logger.info(
            f"Beginning Food.com sampling (target={self.limit:,}, seed={self.seed}, "
            f"dry_run={dry_run}) from: {self.source_path}"
        )

        source_bytes, source_sha = self.source.get_source_metadata()
        tracker = IngestionProgressTracker("foodcom_sampler", "RAW_recipes.csv")

        # ---------------------------------------------------------------------
        # Pass 1: Census and Stratum Population Counts
        # ---------------------------------------------------------------------
        logger.info("Executing Pass 1: Streaming census and stratum profiling...")
        stratum_counts: Dict[str, int] = {}
        seen_ids: Set[str] = set()

        for line_num, row in self.source.open_csv_stream("RAW_recipes.csv"):
            try:
                # Basic validation using the existing validator
                rec = validate_recipe_record(row, line_num)
                if rec.source_id in seen_ids:
                    tracker.record_rejected(line_num, f"Duplicate recipe id: {rec.source_id}", str(row.get("name", "")))
                    continue
                seen_ids.add(rec.source_id)
                tracker.record_accepted()

                stratum_id = determine_foodcom_stratum(row, line_num)
                stratum_counts[stratum_id] = stratum_counts.get(stratum_id, 0) + 1

            except (FoodComValidationError, FoodComParseError) as e:
                tracker.record_rejected(line_num, str(e), str(row.get("name", "")))

        total_valid = tracker.accepted_count
        logger.info(
            f"Pass 1 complete. Scanned: {tracker.total_read:,}, Valid: {total_valid:,}, "
            f"Rejected: {tracker.rejected_count:,}, Discovered Strata: {len(stratum_counts)}"
        )

        # Allocate proportional quotas
        quotas = allocate_proportional_quotas(
            stratum_counts=stratum_counts,
            target_total=self.limit,
            min_stratum_quota=1,
        )

        target_sample_size = sum(quotas.values())

        # If dry-run, construct audit report with planned allocations and return
        if dry_run:
            logger.info("[DRY-RUN] Skipping Pass 2 extraction and disk writing.")
            strata_report: Dict[str, Dict[str, Any]] = {}
            for s_id in sorted(stratum_counts.keys()):
                src_count = stratum_counts[s_id]
                quota = quotas.get(s_id, 0)
                src_pct = (src_count / total_valid * 100) if total_valid > 0 else 0.0
                sample_pct = (quota / target_sample_size * 100) if target_sample_size > 0 else 0.0
                strata_report[s_id] = {
                    "source_count": src_count,
                    "target_quota": quota,
                    "selected_count": quota,
                    "source_percentage": round(src_pct, 2),
                    "sample_percentage": round(sample_pct, 2),
                }

            report = SamplingReport(
                dataset="foodcom",
                source_path=str(self.source_path),
                source_sha256=source_sha if source_sha != "directory_distribution" else None,
                source_byte_size=source_bytes,
                seed=self.seed,
                requested_sample_size=self.limit,
                actual_sample_size=target_sample_size,
                source_rows_scanned=tracker.total_read,
                valid_rows=total_valid,
                rejected_rows=tracker.rejected_count,
                sampling_algorithm="proportional_stratified_reservoir_sampling",
                strata=strata_report,
                sample_rejections=[
                    {"line": r.line_number, "reason": r.reason, "preview": r.sample_preview}
                    for r in tracker.rejections[:10]
                ],
                dry_run=True,
            )
            return report

        # ---------------------------------------------------------------------
        # Pass 2: Reservoir Sampling
        # ---------------------------------------------------------------------
        logger.info(f"Executing Pass 2: Reservoir sampling {target_sample_size:,} recipes...")
        stratified_sampler: StratifiedReservoirSampler[Dict[str, str]] = StratifiedReservoirSampler(
            stratum_quotas=quotas,
            base_seed=self.seed,
        )

        seen_ids_pass2: Set[str] = set()
        for line_num, row in self.source.open_csv_stream("RAW_recipes.csv"):
            try:
                rec = validate_recipe_record(row, line_num)
                if rec.source_id in seen_ids_pass2:
                    continue
                seen_ids_pass2.add(rec.source_id)
                stratum_id = determine_foodcom_stratum(row, line_num)
                stratified_sampler.feed(stratum_id, row)
            except (FoodComValidationError, FoodComParseError):
                continue

        selected_samples_by_stratum = stratified_sampler.get_samples_by_stratum()
        all_selected_recipes = stratified_sampler.get_all_samples()
        selected_recipe_ids: Set[str] = {
            r["id"].strip() for r in all_selected_recipes if r.get("id")
        }

        # ---------------------------------------------------------------------
        # Output Generation: Write Sampled Recipes
        # ---------------------------------------------------------------------
        self.output_dir.mkdir(parents=True, exist_ok=True)
        recipe_out_path = self.output_dir / "RAW_recipes.csv"
        interaction_out_path = self.output_dir / "RAW_interactions.csv"
        report_out_path = self.output_dir / "sampling_report.json"

        recipe_headers = self.source.inspect_headers("RAW_recipes.csv")
        logger.info(f"Writing {len(all_selected_recipes):,} sampled recipes to: {recipe_out_path}")

        try:
            with open(recipe_out_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=recipe_headers)
                writer.writeheader()
                for row in all_selected_recipes:
                    writer.writerow(row)

            recipe_sha = compute_file_sha256(recipe_out_path)
            recipe_size = recipe_out_path.stat().st_size

            # -----------------------------------------------------------------
            # Pass 3: Stream and Filter Interactions
            # -----------------------------------------------------------------
            logger.info("Executing Pass 3: Filtering interactions matching selected recipe IDs...")
            interaction_headers = self.source.inspect_headers("RAW_interactions.csv")
            interactions_scanned = 0
            interactions_retained = 0
            interactions_unmatched = 0
            recipes_with_interactions: Set[str] = set()

            with open(interaction_out_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=interaction_headers)
                writer.writeheader()

                for _, row in self.source.open_csv_stream("RAW_interactions.csv"):
                    interactions_scanned += 1
                    r_id = row.get("recipe_id", "").strip()
                    if r_id in selected_recipe_ids:
                        writer.writerow(row)
                        interactions_retained += 1
                        recipes_with_interactions.add(r_id)
                    else:
                        interactions_unmatched += 1

            interaction_sha = compute_file_sha256(interaction_out_path)
            interaction_size = interaction_out_path.stat().st_size

        except Exception as e:
            # Clean up on failure to prevent corrupted artifacts
            logger.error(f"Error during file writing: {e}. Cleaning up partial files...")
            for p in [recipe_out_path, interaction_out_path]:
                if p.exists():
                    p.unlink()
            raise

        # ---------------------------------------------------------------------
        # Final Report Compilation
        # ---------------------------------------------------------------------
        strata_report = {}
        for s_id in sorted(stratum_counts.keys()):
            src_count = stratum_counts[s_id]
            quota = quotas.get(s_id, 0)
            actual_sel = len(selected_samples_by_stratum.get(s_id, []))
            src_pct = (src_count / total_valid * 100) if total_valid > 0 else 0.0
            sample_pct = (actual_sel / len(all_selected_recipes) * 100) if all_selected_recipes else 0.0
            strata_report[s_id] = {
                "source_count": src_count,
                "target_quota": quota,
                "selected_count": actual_sel,
                "source_percentage": round(src_pct, 2),
                "sample_percentage": round(sample_pct, 2),
            }

        output_metadata = {
            "RAW_recipes.csv": {
                "filename": "RAW_recipes.csv",
                "path": str(recipe_out_path),
                "row_count": len(all_selected_recipes),
                "size_bytes": recipe_size,
                "sha256_checksum": recipe_sha,
            },
            "RAW_interactions.csv": {
                "filename": "RAW_interactions.csv",
                "path": str(interaction_out_path),
                "row_count": interactions_retained,
                "size_bytes": interaction_size,
                "sha256_checksum": interaction_sha,
            },
        }

        interaction_stats = {
            "interactions_scanned": interactions_scanned,
            "interactions_retained": interactions_retained,
            "interactions_unmatched": interactions_unmatched,
            "recipes_with_interactions": len(recipes_with_interactions),
        }

        report = SamplingReport(
            dataset="foodcom",
            source_path=str(self.source_path),
            source_sha256=source_sha if source_sha != "directory_distribution" else None,
            source_byte_size=source_bytes,
            seed=self.seed,
            requested_sample_size=self.limit,
            actual_sample_size=len(all_selected_recipes),
            source_rows_scanned=tracker.total_read,
            valid_rows=total_valid,
            rejected_rows=tracker.rejected_count,
            sampling_algorithm="proportional_stratified_reservoir_sampling",
            strata=strata_report,
            output_files=output_metadata,
            interaction_stats=interaction_stats,
            sample_rejections=[
                {"line": r.line_number, "reason": r.reason, "preview": r.sample_preview}
                for r in tracker.rejections[:10]
            ],
            dry_run=False,
        )

        report.save(report_out_path)
        logger.info(f"Sampling report saved: {report_out_path}")
        return report

