"""FoodFlow Unified Sampling Engine - RecipeNLG Stratified Sampler

Implements reproducible, stratified reservoir sampling for the RecipeNLG corpus.

Stratification dimensions:
  1. Source Origin: Gathered, Recipes1M, Unknown
  2. NER Richness: ner_0 (0 entities), ner_1_3 (1-3 entities), ner_4_8 (4-8 entities), ner_gt_8 (>8 entities)
  3. Directions Availability: directions_usable, directions_empty
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ingestion.config import PROCESSED_DATA_DIR, RECIPENLG_RAW_DIR
from ingestion.datasets.recipenlg.parser import (
    RecipeNLGParseError,
    RecipeNLGSource,
    clean_text,
    safe_parse_list,
)
from ingestion.datasets.recipenlg.validator import (
    DuplicateRecipeIDError,
    RecipeNLGValidationError,
    validate_recipe_record as validate_recipenlg_record,
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
logger = get_logger("sampling.recipenlg")


def classify_source_origin(raw_source: Optional[str]) -> str:
    """Classify the sub-corpus source origin (Gathered, Recipes1M, or Unknown).
    
    Derives source classification strictly and exclusively from the original 'source'
    column. Never infers or substitutes source origin based on recipe IDs.
    
    Verified Encodings:
      - 'Gathered': string 'gathered' (case-insensitive) or encoded class label '1'
      - 'Recipes1M': string 'recipes1m' / 'recipe1m' (case-insensitive) or encoded class label '0'
      - All other, unrecognized, or missing values return 'Unknown'.
    """
    cleaned = clean_text(raw_source)
    if not cleaned:
        return "Unknown"
    lower_s = cleaned.lower()
    if lower_s in ("gathered", "1"):
        return "Gathered"
    elif lower_s in ("recipes1m", "recipe1m", "0"):
        return "Recipes1M"
    return "Unknown"


def classify_ner_richness(raw_ner: Optional[str], line_number: int = 1) -> str:
    """Classify the NER ingredient entity count into richness strata."""
    if not raw_ner:
        return "ner_0"
    try:
        entities = safe_parse_list(raw_ner, "ner", line_number)
        count = len(entities)
        if count == 0:
            return "ner_0"
        elif 1 <= count <= 3:
            return "ner_1_3"
        elif 4 <= count <= 8:
            return "ner_4_8"
        else:
            return "ner_gt_8"
    except RecipeNLGParseError:
        return "ner_0"


def classify_directions_status(raw_directions: Optional[str], line_number: int = 1) -> str:
    """Classify whether the directions field has usable cooking instructions."""
    if not raw_directions:
        return "directions_empty"
    try:
        steps = safe_parse_list(raw_directions, "directions", line_number)
        return "directions_usable" if steps else "directions_empty"
    except RecipeNLGParseError:
        return "directions_empty"


def determine_recipenlg_stratum(row: Dict[str, str], line_number: int = 1) -> str:
    """Compute the composite sampling stratum ID for a RecipeNLG recipe row.
    
    Composite format: '{source_origin}__{ner_richness}__{directions_status}'
    """
    source_origin = classify_source_origin(row.get("source"))
    ner_richness = classify_ner_richness(row.get("NER") or row.get("ner"), line_number)
    raw_dirs = row.get("directions") or row.get("steps")
    directions_status = classify_directions_status(raw_dirs, line_number)

    return f"{source_origin}__{ner_richness}__{directions_status}"


class RecipeNLGSampler:
    """Orchestrates memory-bounded stratified sampling for RecipeNLG."""

    def __init__(
        self,
        source_path: Path,
        output_dir: Optional[Path] = None,
        limit: int = 25000,
        seed: int = 42,
    ):
        self.source_path = Path(source_path).resolve()
        self.source = RecipeNLGSource(self.source_path)
        self.limit = max(0, limit)
        self.seed = seed

        if output_dir:
            self.output_dir = Path(output_dir).resolve()
        else:
            self.output_dir = (PROCESSED_DATA_DIR / "dev_sample" / "recipenlg").resolve()

    def run(self, dry_run: bool = False) -> SamplingReport:
        """Execute the two-pass stratified sampling workflow for RecipeNLG."""
        logger.info(
            f"Beginning RecipeNLG sampling (target={self.limit:,}, seed={self.seed}, "
            f"dry_run={dry_run}) from: {self.source_path}"
        )

        source_bytes, source_sha = self.source.get_source_metadata()
        tracker = IngestionProgressTracker("recipenlg_sampler", "full_dataset.csv")

        # ---------------------------------------------------------------------
        # Pass 1: Census and Stratum Population Counts
        # ---------------------------------------------------------------------
        logger.info("Executing Pass 1: Streaming census and stratum profiling...")
        stratum_counts: Dict[str, int] = {}
        seen_ids: Set[str] = set()

        for line_num, row in self.source.open_csv_stream("full_dataset.csv"):
            try:
                validate_recipenlg_record(row, line_num, seen_ids=seen_ids)
                tracker.record_accepted()

                stratum_id = determine_recipenlg_stratum(row, line_num)
                stratum_counts[stratum_id] = stratum_counts.get(stratum_id, 0) + 1

            except (RecipeNLGValidationError, RecipeNLGParseError, DuplicateRecipeIDError) as e:
                tracker.record_rejected(line_num, str(e), str(row.get("title", "")))

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
                dataset="recipenlg",
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
        for line_num, row in self.source.open_csv_stream("full_dataset.csv"):
            try:
                validate_recipenlg_record(row, line_num, seen_ids=seen_ids_pass2)
                stratum_id = determine_recipenlg_stratum(row, line_num)
                stratified_sampler.feed(stratum_id, row)
            except (RecipeNLGValidationError, RecipeNLGParseError, DuplicateRecipeIDError):
                continue

        selected_samples_by_stratum = stratified_sampler.get_samples_by_stratum()
        all_selected_recipes = stratified_sampler.get_all_samples()

        # ---------------------------------------------------------------------
        # Output Generation: Write Sampled Recipes
        # ---------------------------------------------------------------------
        self.output_dir.mkdir(parents=True, exist_ok=True)
        recipe_out_path = self.output_dir / "full_dataset.csv"
        report_out_path = self.output_dir / "sampling_report.json"

        recipe_headers = self.source.inspect_headers("full_dataset.csv")
        logger.info(f"Writing {len(all_selected_recipes):,} sampled recipes to: {recipe_out_path}")

        try:
            with open(recipe_out_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=recipe_headers)
                writer.writeheader()
                for row in all_selected_recipes:
                    writer.writerow(row)

            recipe_sha = compute_file_sha256(recipe_out_path)
            recipe_size = recipe_out_path.stat().st_size

        except Exception as e:
            logger.error(f"Error during RecipeNLG sample writing: {e}. Cleaning up partial files...")
            if recipe_out_path.exists():
                recipe_out_path.unlink()
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
            "full_dataset.csv": {
                "filename": "full_dataset.csv",
                "path": str(recipe_out_path),
                "row_count": len(all_selected_recipes),
                "size_bytes": recipe_size,
                "sha256_checksum": recipe_sha,
            },
        }

        report = SamplingReport(
            dataset="recipenlg",
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
            sample_rejections=[
                {"line": r.line_number, "reason": r.reason, "preview": r.sample_preview}
                for r in tracker.rejections[:10]
            ],
            dry_run=False,
        )

        report.save(report_out_path)
        logger.info(f"Sampling report saved: {report_out_path}")
        return report
