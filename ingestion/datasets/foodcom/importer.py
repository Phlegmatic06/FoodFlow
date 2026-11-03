"""Food.com Ingestion Pipeline Orchestrator

Coordinates file discovery, header verification, streaming recipe validation,
batch database loading with FTS vector generation, ratings aggregation via
temporary staging tables, quality report generation, and manifest auditing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.config import (
    DATASET_REGISTRY,
    DEFAULT_BATCH_SIZE,
    REPORTS_DIR,
    get_database_url,
)
from ingestion.database import DatabaseConnectionError, get_connection
from ingestion.datasets.foodcom.loader import FoodComLoader
from ingestion.datasets.foodcom.parser import FoodComParseError, FoodComSource
from ingestion.datasets.foodcom.ratings import RatingsAggregationMetrics, RatingsAggregator
from ingestion.datasets.foodcom.validator import (
    FoodComValidationError,
    ValidatedRecipe,
    validate_headers,
    validate_recipe_record,
)
from ingestion.logging_config import get_logger, log_rejected_row
from ingestion.manifest import (
    STATUS_COMPLETED,
    STATUS_PARTIALLY_IMPORTED,
    load_manifest,
    record_ingestion_failure,
    record_verified_file,
    save_manifest,
)
from ingestion.utils.csv_utils import batch_iterator


logger = get_logger("foodcom.importer")


@dataclass
class FoodComReport:
    component: str
    source_path: str
    dry_run: bool
    status: str
    started_at: str
    completed_at: Optional[str] = None
    recipe_metrics: Dict[str, Any] = field(default_factory=dict)
    interaction_metrics: Dict[str, Any] = field(default_factory=dict)
    sample_rejections: List[Dict[str, Any]] = field(default_factory=list)
    report_file_path: Optional[str] = None
    error_message: Optional[str] = None


class FoodComImporter:
    """Orchestrates end-to-end ingestion of Food.com recipes and interaction ratings."""

    def __init__(
        self,
        source_path: Path,
        component: str = "all",
        batch_size: int = DEFAULT_BATCH_SIZE,
        dry_run: bool = False,
        limit_recipes: Optional[int] = None,
        limit_interactions: Optional[int] = None,
        database_url: Optional[str] = None,
    ):
        self.source_path = Path(source_path).resolve()
        self.component = component.lower().strip()
        if self.component not in ("recipes", "interactions", "all"):
            raise ValueError(f"Invalid component: {component!r}. Choose from: recipes, interactions, all")

        self.batch_size = max(1, batch_size)
        self.dry_run = dry_run
        self.limit_recipes = limit_recipes
        self.limit_interactions = limit_interactions
        self.database_url = database_url or get_database_url()

        self.source = FoodComSource(self.source_path)
        self.meta = DATASET_REGISTRY["foodcom"]

    def preflight_check(self) -> None:
        """Verify that required files and CSV column headers exist in the source."""
        if self.component in ("recipes", "all"):
            if not self.source.has_file("raw_recipes.csv"):
                raise FoodComParseError(
                    f"Food.com source '{self.source_path}' is missing required file 'RAW_recipes.csv'. "
                    f"Available: {self.source.list_available_files()}"
                )
            headers = self.source.inspect_headers("raw_recipes.csv")
            ok, missing = validate_headers("raw_recipes.csv", headers)
            if not ok:
                raise FoodComParseError(f"RAW_recipes.csv is missing required headers: {missing}")

        if self.component in ("interactions", "all"):
            if not self.source.has_file("raw_interactions.csv"):
                raise FoodComParseError(
                    f"Food.com source '{self.source_path}' is missing required file 'RAW_interactions.csv'. "
                    f"Available: {self.source.list_available_files()}"
                )
            headers = self.source.inspect_headers("raw_interactions.csv")
            ok, missing = validate_headers("raw_interactions.csv", headers)
            if not ok:
                raise FoodComParseError(f"RAW_interactions.csv is missing required headers: {missing}")

    def run(self) -> FoodComReport:
        """Execute the ingestion process according to configured component."""
        logger.info(
            f"Beginning Food.com ingestion (component={self.component!r}, "
            f"dry_run={self.dry_run}, batch_size={self.batch_size}) from {self.source_path}"
        )

        self.preflight_check()

        if not self.dry_run and not self.database_url:
            raise DatabaseConnectionError(
                "DATABASE_URL is not set. Cannot run live ingestion without a configured PostgreSQL connection.\n"
                "Specify --dry-run to validate and parse local data without writing to the database."
            )

        report = FoodComReport(
            component=self.component,
            source_path=str(self.source_path),
            dry_run=self.dry_run,
            status="pending",
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            if self.dry_run:
                self._run_dry_run(report)
                report.status = "dry_run_passed"
            else:
                self._run_live(report)
                report.status = "completed"

            report.completed_at = datetime.now(timezone.utc).isoformat()
            self._write_quality_report(report)
            return report

        except Exception as e:
            report.status = "failed"
            report.error_message = str(e)
            report.completed_at = datetime.now(timezone.utc).isoformat()
            self._write_quality_report(report)
            if not self.dry_run:
                try:
                    record_ingestion_failure("foodcom", f"run_{self.component}", str(e))
                except Exception:
                    pass
            raise

    def _run_dry_run(self, report: FoodComReport) -> None:
        """Perform streaming validation without making database modifications."""
        logger.info("[DRY-RUN] Executing streaming validation...")
        dry_run_known_recipes: Set[str] = set()

        # 1. Validate Recipes
        if self.component in ("recipes", "all"):
            logger.info("[DRY-RUN] Validating RAW_recipes.csv...")
            recipe_total = 0
            recipe_accepted = 0
            recipe_rejected = 0

            for line_num, row in self.source.open_csv_stream("raw_recipes.csv"):
                if self.limit_recipes and recipe_accepted >= self.limit_recipes:
                    break
                recipe_total += 1
                try:
                    rec = validate_recipe_record(row, line_num)
                    dry_run_known_recipes.add(rec.id)
                    recipe_accepted += 1
                except FoodComValidationError as ve:
                    recipe_rejected += 1
                    self._record_rejection(report, "RAW_recipes.csv", ve.line_number, ve.reason, row)

            report.recipe_metrics = {
                "total_rows_read": recipe_total,
                "accepted_recipes": recipe_accepted,
                "rejected_recipes": recipe_rejected,
            }

        # 2. Validate Interactions
        if self.component in ("interactions", "all"):
            logger.info("[DRY-RUN] Validating RAW_interactions.csv...")
            aggregator = RatingsAggregator(connection=None, batch_size=self.batch_size)
            metrics = aggregator.process_interactions_stream(
                interactions_stream=self.source.open_csv_stream("raw_interactions.csv"),
                known_recipe_ids=dry_run_known_recipes if self.component == "all" else None,
                dry_run=True,
                limit=self.limit_interactions,
            )
            report.interaction_metrics = asdict(metrics)

    def _run_live(self, report: FoodComReport) -> None:
        """Stream, validate, and persist records into PostgreSQL 16."""
        with get_connection(self.database_url, autocommit=False) as conn:
            loader = FoodComLoader(conn)
            canonical_map = loader.fetch_canonical_ingredient_map()

            imported_counts: Dict[str, int] = {}

            # Phase 1: Ingest Recipes
            if self.component in ("recipes", "all"):
                logger.info("Importing RAW_recipes.csv into recipe_catalog...")
                recipe_total = 0
                recipe_accepted = 0
                recipe_rejected = 0
                batch: List[ValidatedRecipe] = []

                totals = {
                    "recipes": 0,
                    "recipe_ingredients": 0,
                    "recipe_instructions": 0,
                    "recipe_tags": 0,
                    "recipe_nutrition_raw": 0,
                }

                for line_num, row in self.source.open_csv_stream("raw_recipes.csv"):
                    if self.limit_recipes and recipe_accepted >= self.limit_recipes:
                        break
                    recipe_total += 1
                    try:
                        rec = validate_recipe_record(row, line_num)
                        batch.append(rec)
                        recipe_accepted += 1

                        if len(batch) >= self.batch_size:
                            b_counts = loader.load_recipes_batch(batch, canonical_map)
                            for k, v in b_counts.items():
                                totals[k] += v
                            batch = []
                    except FoodComValidationError as ve:
                        recipe_rejected += 1
                        self._record_rejection(report, "RAW_recipes.csv", ve.line_number, ve.reason, row)

                if batch:
                    b_counts = loader.load_recipes_batch(batch, canonical_map)
                    for k, v in b_counts.items():
                        totals[k] += v

                report.recipe_metrics = {
                    "total_rows_read": recipe_total,
                    "accepted_recipes": recipe_accepted,
                    "rejected_recipes": recipe_rejected,
                    "inserted_totals": totals,
                }
                imported_counts.update(totals)

                # Record recipes provenance
                size_bytes, sha256_hash = self.source.get_source_metadata()
                loader.record_provenance(
                    component_name="Recipes",
                    source_url=self.meta.official_source_url,
                    release_version=self.meta.source_version or "2019 Snapshot",
                    file_name="RAW_recipes.csv",
                    sha256_checksum=sha256_hash,
                    total_rows=recipe_total,
                    imported_rows=recipe_accepted,
                    rejected_rows=recipe_rejected,
                    notes=f"Ingested via FoodFlow CLI (batch_size={self.batch_size})",
                )

            # Phase 2: Ingest Ratings / Interactions
            if self.component in ("interactions", "all"):
                logger.info("Aggregating RAW_interactions.csv into recipe_catalog.recipe_ratings...")
                known_recipes = loader.fetch_existing_foodcom_recipe_ids()

                aggregator = RatingsAggregator(connection=conn, batch_size=self.batch_size)
                metrics = aggregator.process_interactions_stream(
                    interactions_stream=self.source.open_csv_stream("raw_interactions.csv"),
                    known_recipe_ids=known_recipes,
                    dry_run=False,
                    limit=self.limit_interactions,
                )
                report.interaction_metrics = asdict(metrics)
                imported_counts["recipe_ratings"] = metrics.updated_recipes_count

                # Record interactions provenance
                loader.record_provenance(
                    component_name="Interactions & Ratings",
                    source_url=self.meta.official_source_url,
                    release_version=self.meta.source_version or "2019 Snapshot",
                    file_name="RAW_interactions.csv",
                    sha256_checksum="streaming_aggregation",
                    total_rows=metrics.total_rows,
                    imported_rows=metrics.updated_recipes_count,
                    rejected_rows=metrics.invalid_ratings,
                    notes=f"Aggregated ratings (valid={metrics.valid_ratings:,}, unmatched={metrics.unmatched_ratings:,})",
                )

            # Update Manifest
            self._update_manifest(imported_counts)

    def _update_manifest(self, imported_counts: Dict[str, int]) -> None:
        """Update data/manifest.json with verified metadata and imported counts."""
        manifest = load_manifest()
        entry = manifest.datasets["foodcom"]
        entry.imported_row_counts.update(imported_counts)

        # Status transition logic
        if self.component == "all":
            entry.import_status = STATUS_COMPLETED
        else:
            entry.import_status = STATUS_PARTIALLY_IMPORTED

        entry.last_successful_ingestion = datetime.now(timezone.utc).isoformat()
        entry.failure_record = None
        save_manifest(manifest)

    def _record_rejection(
        self,
        report: FoodComReport,
        file_name: str,
        line_num: int,
        reason: str,
        raw_row: Dict[str, str],
    ) -> None:
        """Capture malformed row details for reporting and logging."""
        if len(report.sample_rejections) < 25:
            sample_str = str(dict(list(raw_row.items())[:6]))
            report.sample_rejections.append({
                "file": file_name,
                "line": line_num,
                "reason": reason,
                "sample": sample_str,
            })
            log_rejected_row(
                logger=logger,
                dataset="food_com",
                file_name=file_name,
                line_number=line_num,
                reason=reason,
                raw_sample=sample_str,
            )

    def _write_quality_report(self, report: FoodComReport) -> None:
        """Persist structured JSON report into data/reports/."""
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            report_file = REPORTS_DIR / f"foodcom_ingestion_{ts}.json"
            report.report_file_path = str(report_file)

            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
            logger.info(f"Audit report saved: {report_file}")
        except Exception as e:
            logger.warning(f"Failed to write ingestion audit report: {e}")

