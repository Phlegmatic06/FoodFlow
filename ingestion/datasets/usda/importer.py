"""USDA FoodData Central Ingestion Pipeline Orchestrator

Coordinates file discovery, header verification, streaming validation,
dependency-ordered database loading, and manifest auditing for:
  - Foundation Foods (October 2026)
  - SR Legacy (April 2018)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ingestion.config import (
    DEFAULT_BATCH_SIZE,
    USDA_COLLECTIONS,
    USDACollectionMetadata,
    get_database_url,
    mask_database_url,
    resolve_usda_collection_key,
)
from ingestion.database import DatabaseConnectionError, get_connection
from ingestion.datasets.usda.loader import USDALoader
from ingestion.datasets.usda.parser import USDAParseError, USDASource
from ingestion.datasets.usda.validator import (
    USDAValidationError,
    ValidatedFood,
    ValidatedFoodNutrient,
    ValidatedFoodPortion,
    ValidatedNutrient,
    validate_food_nutrient_record,
    validate_food_portion_record,
    validate_food_record,
    validate_headers,
    validate_nutrient_record,
)
from ingestion.logging_config import get_logger, log_rejected_row
from ingestion.manifest import (
    record_collection_failure,
    record_collection_file,
    record_collection_success,
)
from ingestion.utils.checksums import format_bytes
from ingestion.utils.csv_utils import batch_iterator


logger = get_logger("usda.importer")


@dataclass
class IngestionReport:
    collection_id: str
    display_name: str
    source_path: str
    dry_run: bool
    status: str
    imported_counts: Dict[str, int] = field(default_factory=dict)
    rejected_counts: Dict[str, int] = field(default_factory=dict)
    sample_rejections: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None


class USDAImporter:
    """Orchestrates end-to-end ingestion of USDA Foundation Foods or SR Legacy."""

    def __init__(
        self,
        source_path: Path,
        collection_type: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        dry_run: bool = False,
        limit: Optional[int] = None,
        database_url: Optional[str] = None,
    ):
        self.source_path = Path(source_path).resolve()
        resolved_coll = resolve_usda_collection_key(collection_type)
        if not resolved_coll or resolved_coll not in USDA_COLLECTIONS:
            raise ValueError(
                f"Unknown USDA collection: {collection_type!r}. "
                f"Choose from: {', '.join(USDA_COLLECTIONS.keys())}"
            )
        self.collection_meta: USDACollectionMetadata = USDA_COLLECTIONS[resolved_coll]
        self.collection_id = resolved_coll
        self.batch_size = max(1, batch_size)
        self.dry_run = dry_run
        self.limit = limit
        self.database_url = database_url or get_database_url()

        self.source = USDASource(self.source_path)

    def preflight_check(self) -> None:
        """Verify that all required files and column headers exist in the source."""
        required = ["food.csv", "nutrient.csv", "food_nutrient.csv"]
        missing_files = [f for f in required if not self.source.has_file(f)]
        if missing_files:
            raise USDAParseError(
                f"USDA source '{self.source_path}' is missing required files: {missing_files}. "
                f"Available files: {self.source.list_available_files()}"
            )

        for fname in required:
            headers = self.source.inspect_headers(fname)
            ok, missing_headers = validate_headers(fname, headers)
            if not ok:
                raise USDAParseError(
                    f"File '{fname}' in USDA source '{self.source_path}' is missing required headers: {missing_headers}"
                )

        if self.source.has_file("food_portion.csv"):
            portion_headers = self.source.inspect_headers("food_portion.csv")
            ok, missing_headers = validate_headers("food_portion.csv", portion_headers)
            if not ok:
                logger.warning(
                    f"Optional file 'food_portion.csv' is missing recommended headers: {missing_headers}. "
                    f"Portion ingestion will be skipped."
                )

    def run(self) -> IngestionReport:
        """Execute the ingestion pipeline."""
        logger.info(
            f"Beginning USDA ingestion for [{self.collection_meta.display_name}] from {self.source_path} "
            f"(dry_run={self.dry_run}, batch_size={self.batch_size}, limit={self.limit})"
        )

        self.preflight_check()

        # Database readiness check
        if not self.dry_run:
            if not self.database_url:
                raise DatabaseConnectionError(
                    "DATABASE_URL is not set. Cannot run live ingestion without a configured PostgreSQL connection.\n"
                    "Specify --dry-run to validate and parse local data without writing to the database."
                )

        report = IngestionReport(
            collection_id=self.collection_id,
            display_name=self.collection_meta.display_name,
            source_path=str(self.source_path),
            dry_run=self.dry_run,
            status="pending",
        )

        try:
            if self.dry_run:
                self._run_dry_run(report)
                report.status = "dry_run_passed"
            else:
                self._run_live(report)
                report.status = "completed"
            return report
        except Exception as e:
            report.status = "failed"
            report.error_message = str(e)
            if not self.dry_run:
                try:
                    record_collection_failure(
                        dataset_key="usda",
                        collection_id=self.collection_id,
                        step="run",
                        error_message=str(e),
                    )
                except Exception:
                    pass
            raise

    def _run_dry_run(self, report: IngestionReport) -> None:
        """Validate and parse records in memory without database modifications."""
        logger.info("[DRY-RUN] Executing streaming validation and parsing...")
        known_foods: Set[int] = set()
        known_nutrients: Set[int] = set()

        # 1. Validate Foods
        food_accepted = 0
        food_rejected = 0
        for line_num, row in self.source.open_csv_stream("food.csv"):
            if self.limit and food_accepted >= self.limit:
                break
            try:
                food = validate_food_record(row, line_num, self.collection_meta.data_type_tag)
                known_foods.add(food.fdc_id)
                food_accepted += 1
            except USDAValidationError as ve:
                food_rejected += 1
                self._record_rejection(report, "food.csv", ve.line_number, ve.reason, row)

        report.imported_counts["usda_foods"] = food_accepted
        report.rejected_counts["food.csv"] = food_rejected

        # 2. Validate Nutrients
        nut_accepted = 0
        nut_rejected = 0
        for line_num, row in self.source.open_csv_stream("nutrient.csv"):
            try:
                nut = validate_nutrient_record(row, line_num)
                known_nutrients.add(nut.id)
                nut_accepted += 1
            except USDAValidationError as ve:
                nut_rejected += 1
                self._record_rejection(report, "nutrient.csv", ve.line_number, ve.reason, row)

        report.imported_counts["usda_nutrients"] = nut_accepted
        report.rejected_counts["nutrient.csv"] = nut_rejected

        # 3. Validate Food Nutrients
        fn_accepted = 0
        fn_rejected = 0
        for line_num, row in self.source.open_csv_stream("food_nutrient.csv"):
            try:
                validate_food_nutrient_record(row, line_num, known_foods, known_nutrients)
                fn_accepted += 1
            except USDAValidationError as ve:
                fn_rejected += 1
                self._record_rejection(report, "food_nutrient.csv", ve.line_number, ve.reason, row)

        report.imported_counts["usda_food_nutrients"] = fn_accepted
        report.rejected_counts["food_nutrient.csv"] = fn_rejected

        # 4. Validate Food Portions (optional)
        fp_accepted = 0
        fp_rejected = 0
        if self.source.has_file("food_portion.csv"):
            for line_num, row in self.source.open_csv_stream("food_portion.csv"):
                try:
                    validate_food_portion_record(row, line_num, known_foods)
                    fp_accepted += 1
                except USDAValidationError as ve:
                    fp_rejected += 1
                    self._record_rejection(report, "food_portion.csv", ve.line_number, ve.reason, row)

            report.imported_counts["usda_food_portions"] = fp_accepted
            report.rejected_counts["food_portion.csv"] = fp_rejected

        logger.info(
            f"[DRY-RUN] Finished validation: "
            f"Foods: {food_accepted} accepted ({food_rejected} rejected), "
            f"Nutrients: {nut_accepted} accepted ({nut_rejected} rejected), "
            f"Food Nutrients: {fn_accepted} accepted ({fn_rejected} rejected), "
            f"Portions: {fp_accepted} accepted ({fp_rejected} rejected)."
        )

    def _run_live(self, report: IngestionReport) -> None:
        """Stream, validate, and persist records into PostgreSQL 16 under foodflow_admin."""
        with get_connection(self.database_url, autocommit=False) as conn:
            loader = USDALoader(conn)

            # Pre-seed known IDs from existing database records to support incremental imports
            known_foods: Set[int] = loader.fetch_existing_food_ids()
            known_nutrients: Set[int] = loader.fetch_existing_nutrient_ids()

            # -------------------------------------------------------------
            # Step 1: Foods
            # -------------------------------------------------------------
            logger.info("Importing usda_foods...")
            food_batch: List[ValidatedFood] = []
            food_accepted = 0
            food_rejected = 0

            for line_num, row in self.source.open_csv_stream("food.csv"):
                if self.limit and food_accepted >= self.limit:
                    break
                try:
                    food = validate_food_record(row, line_num, self.collection_meta.data_type_tag)
                    food_batch.append(food)
                    known_foods.add(food.fdc_id)
                    food_accepted += 1
                    if len(food_batch) >= self.batch_size:
                        loader.load_foods(food_batch)
                        food_batch = []
                except USDAValidationError as ve:
                    food_rejected += 1
                    self._record_rejection(report, "food.csv", ve.line_number, ve.reason, row)

            if food_batch:
                loader.load_foods(food_batch)

            report.imported_counts["usda_foods"] = food_accepted
            report.rejected_counts["food.csv"] = food_rejected

            # -------------------------------------------------------------
            # Step 2: Nutrients
            # -------------------------------------------------------------
            logger.info("Importing usda_nutrients...")
            nut_batch: List[ValidatedNutrient] = []
            nut_accepted = 0
            nut_rejected = 0

            for line_num, row in self.source.open_csv_stream("nutrient.csv"):
                try:
                    nut = validate_nutrient_record(row, line_num)
                    nut_batch.append(nut)
                    known_nutrients.add(nut.id)
                    nut_accepted += 1
                    if len(nut_batch) >= self.batch_size:
                        loader.load_nutrients(nut_batch)
                        nut_batch = []
                except USDAValidationError as ve:
                    nut_rejected += 1
                    self._record_rejection(report, "nutrient.csv", ve.line_number, ve.reason, row)

            if nut_batch:
                loader.load_nutrients(nut_batch)

            report.imported_counts["usda_nutrients"] = nut_accepted
            report.rejected_counts["nutrient.csv"] = nut_rejected

            # -------------------------------------------------------------
            # Step 3: Food Nutrients
            # -------------------------------------------------------------
            logger.info("Importing usda_food_nutrients...")
            fn_batch: List[ValidatedFoodNutrient] = []
            fn_accepted = 0
            fn_rejected = 0

            for line_num, row in self.source.open_csv_stream("food_nutrient.csv"):
                try:
                    fn = validate_food_nutrient_record(row, line_num, known_foods, known_nutrients)
                    fn_batch.append(fn)
                    fn_accepted += 1
                    if len(fn_batch) >= self.batch_size:
                        loader.load_food_nutrients(fn_batch)
                        fn_batch = []
                except USDAValidationError as ve:
                    fn_rejected += 1
                    self._record_rejection(report, "food_nutrient.csv", ve.line_number, ve.reason, row)

            if fn_batch:
                loader.load_food_nutrients(fn_batch)

            report.imported_counts["usda_food_nutrients"] = fn_accepted
            report.rejected_counts["food_nutrient.csv"] = fn_rejected

            # -------------------------------------------------------------
            # Step 4: Food Portions
            # -------------------------------------------------------------
            fp_accepted = 0
            fp_rejected = 0
            if self.source.has_file("food_portion.csv"):
                logger.info("Importing usda_food_portions...")
                fp_batch: List[ValidatedFoodPortion] = []
                for line_num, row in self.source.open_csv_stream("food_portion.csv"):
                    try:
                        fp = validate_food_portion_record(row, line_num, known_foods)
                        fp_batch.append(fp)
                        fp_accepted += 1
                        if len(fp_batch) >= self.batch_size:
                            loader.load_food_portions(fp_batch)
                            fp_batch = []
                    except USDAValidationError as ve:
                        fp_rejected += 1
                        self._record_rejection(report, "food_portion.csv", ve.line_number, ve.reason, row)

                if fp_batch:
                    loader.load_food_portions(fp_batch)

                report.imported_counts["usda_food_portions"] = fp_accepted
                report.rejected_counts["food_portion.csv"] = fp_rejected

            # -------------------------------------------------------------
            # Step 5: Audit & Provenance
            # -------------------------------------------------------------
            size_bytes, sha256_hash = self.source.get_source_metadata()
            total_imported = sum(report.imported_counts.values())
            total_rejected = sum(report.rejected_counts.values())

            loader.record_provenance(
                collection_name=self.collection_meta.display_name,
                source_url=self.collection_meta.official_source_url,
                release_date=self.collection_meta.release_date,
                file_name=self.source_path.name,
                sha256_checksum=sha256_hash,
                total_rows=total_imported + total_rejected,
                imported_rows=total_imported,
                rejected_rows=total_rejected,
                notes=f"Ingested via NutriPod CLI (batch_size={self.batch_size})",
            )

            # Record in manifest
            record_collection_success(
                dataset_key="usda",
                collection_id=self.collection_id,
                imported_counts=report.imported_counts,
                rejected_counts=report.rejected_counts,
            )

        logger.info(
            f"Successfully completed live USDA ingestion for [{self.collection_meta.display_name}]: "
            f"Imported {sum(report.imported_counts.values()):,} total records."
        )

    def _record_rejection(
        self,
        report: IngestionReport,
        file_name: str,
        line_num: int,
        reason: str,
        raw_row: Dict[str, str],
    ) -> None:
        """Log rejection and capture a representative sample."""
        if len(report.sample_rejections) < 20:
            sample_str = str(dict(list(raw_row.items())[:6]))
            report.sample_rejections.append({
                "file": file_name,
                "line": line_num,
                "reason": reason,
                "sample": sample_str,
            })
            log_rejected_row(
                logger=logger,
                dataset="usda",
                file_name=file_name,
                line_number=line_num,
                reason=reason,
                raw_sample=sample_str,
            )

