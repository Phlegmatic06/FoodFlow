"""RecipeNLG Ingestion Pipeline Orchestrator

Coordinates file discovery, header verification, streaming recipe validation,
conservative ingredient canonical linking, full-text search vector generation,
quality report generation, and manifest auditing for RecipeNLG (~2.23M records).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ingestion.config import (
    DATASET_REGISTRY,
    DEFAULT_BATCH_SIZE,
    REPORTS_DIR,
    get_database_url,
)
from ingestion.database import DatabaseConnectionError, get_connection
from ingestion.datasets.recipenlg.loader import RecipeNLGLoader
from ingestion.datasets.recipenlg.parser import RecipeNLGParseError, RecipeNLGSource
from ingestion.datasets.recipenlg.validator import (
    DuplicateRecipeIDError,
    RecipeNLGValidationError,
    ValidatedRecipeNLG,
    validate_headers,
    validate_recipe_record,
)
from ingestion.logging_config import get_logger, log_rejected_row
from ingestion.manifest import (
    STATUS_COMPLETED,
    load_manifest,
    record_ingestion_failure,
    record_ingestion_success,
    record_verified_file,
    save_manifest,
)


logger = get_logger("recipenlg.importer")


@dataclass
class RecipeNLGReport:
    """Execution metrics and audit summary for a RecipeNLG ingestion run."""

    source_path: str
    dry_run: bool
    status: str
    started_at: str
    completed_at: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    sample_rejections: List[Dict[str, Any]] = field(default_factory=list)
    report_file_path: Optional[str] = None
    error_message: Optional[str] = None


class RecipeNLGImporter:
    """Orchestrates end-to-end ingestion of the RecipeNLG large-scale recipe corpus."""

    def __init__(
        self,
        source_path: Path,
        batch_size: int = DEFAULT_BATCH_SIZE,
        dry_run: bool = False,
        limit: Optional[int] = None,
        database_url: Optional[str] = None,
        force: bool = False,
    ):
        self.source_path = Path(source_path).resolve()
        self.batch_size = max(1, batch_size)
        self.dry_run = dry_run
        self.limit = limit
        self.database_url = database_url or get_database_url()
        self.force = force

        self.source = RecipeNLGSource(self.source_path)
        self.meta = DATASET_REGISTRY["recipenlg"]

    def preflight_check(self) -> None:
        """Verify that source files and required column headers exist."""
        if not self.source.has_file("full_dataset.csv"):
            raise RecipeNLGParseError(
                f"RecipeNLG source '{self.source_path}' is missing required file 'full_dataset.csv'. "
                f"Available: {self.source.list_available_files()}"
            )
        headers = self.source.inspect_headers("full_dataset.csv")
        ok, missing = validate_headers(headers)
        if not ok:
            raise RecipeNLGParseError(f"full_dataset.csv is missing required headers: {missing}")

    def run(self) -> RecipeNLGReport:
        """Execute the RecipeNLG ingestion process."""
        logger.info(
            f"Beginning RecipeNLG ingestion (dry_run={self.dry_run}, "
            f"batch_size={self.batch_size}, limit={self.limit}) from {self.source_path}"
        )

        self.preflight_check()

        report = RecipeNLGReport(
            source_path=str(self.source_path),
            dry_run=self.dry_run,
            status="running",
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
                    record_ingestion_failure("recipenlg", "run", str(e))
                except Exception:
                    pass
            raise

    def _record_rejection(
        self,
        report: RecipeNLGReport,
        file_name: str,
        line_num: int,
        reason: str,
        row: Dict[str, Any],
    ) -> None:
        """Log rejected row details and retain sample in report."""
        log_rejected_row(logger, "recipenlg", file_name, line_num, reason, str(row))
        if len(report.sample_rejections) < 20:
            clean_sample = {k: v[:60] if isinstance(v, str) else v for k, v in list(row.items())[:6]}
            report.sample_rejections.append({
                "file": file_name,
                "line": line_num,
                "reason": reason,
                "sample": clean_sample,
            })

    def _run_dry_run(self, report: RecipeNLGReport) -> None:
        """Perform streaming validation without making database modifications."""
        logger.info("[DRY-RUN] Executing streaming validation of RecipeNLG...")
        seen_ids: Set[str] = set()

        total_rows = 0
        accepted_recipes = 0
        rejected_rows = 0
        duplicate_source_ids = 0
        empty_titles = 0
        missing_or_malformed_ingredients = 0
        malformed_directions = 0
        missing_directions_recipes = 0
        ner_failures = 0
        unknown_sources = 0

        for line_num, row in self.source.open_csv_stream("full_dataset.csv"):
            if self.limit and accepted_recipes >= self.limit:
                break
            total_rows += 1
            try:
                rec = validate_recipe_record(row, line_num, seen_ids=seen_ids)
                accepted_recipes += 1

                if rec.has_ner_failure:
                    ner_failures += 1
                if rec.has_missing_directions:
                    missing_directions_recipes += 1
                if rec.source_origin not in ("Gathered", "Recipes1M"):
                    unknown_sources += 1

            except DuplicateRecipeIDError as de:
                rejected_rows += 1
                duplicate_source_ids += 1
                self._record_rejection(report, "full_dataset.csv", de.line_number, de.reason, row)
            except RecipeNLGValidationError as ve:
                rejected_rows += 1
                if ve.field_name == "title":
                    empty_titles += 1
                elif ve.field_name == "ingredients":
                    missing_or_malformed_ingredients += 1
                elif ve.field_name == "directions":
                    malformed_directions += 1
                self._record_rejection(report, "full_dataset.csv", ve.line_number, ve.reason, row)

        report.metrics = {
            "total_source_rows": total_rows,
            "accepted_recipes": accepted_recipes,
            "rejected_rows": rejected_rows,
            "duplicate_source_ids": duplicate_source_ids,
            "empty_titles": empty_titles,
            "missing_or_malformed_ingredients": missing_or_malformed_ingredients,
            "malformed_directions": malformed_directions,
            "missing_directions_recipes": missing_directions_recipes,
            "ner_failures": ner_failures,
            "unknown_source_classifications": unknown_sources,
            "canonical_links": 0,
            "ambiguous_ingredient_matches": 0,
        }

    def _run_live(self, report: RecipeNLGReport) -> None:
        """Stream, validate, and persist RecipeNLG records into PostgreSQL 16."""
        if not self.database_url:
            raise DatabaseConnectionError("DATABASE_URL is not set. Cannot run live ingestion.")

        with get_connection(self.database_url, autocommit=False) as conn:
            loader = RecipeNLGLoader(conn)
            canonical_map = loader.fetch_canonical_ingredient_map()
            has_source_origin = loader.check_source_origin_column_exists()

            if not has_source_origin:
                msg = (
                    "Column 'source_origin' does not exist in 'recipe_catalog.recipes'. "
                    "Please apply migration 'database/migrations/005_add_recipenlg_source_origin.sql' "
                    "before running live RecipeNLG ingestion."
                )
                if not self.force:
                    raise DatabaseConnectionError(msg)
                else:
                    logger.warning(f"[FORCE MODE] {msg} Proceeding without source_origin column.")

            seen_ids: Set[str] = set()
            total_rows = 0
            accepted_recipes = 0
            rejected_rows = 0
            duplicate_source_ids = 0
            empty_titles = 0
            missing_or_malformed_ingredients = 0
            malformed_directions = 0
            missing_directions_recipes = 0
            ner_failures = 0
            unknown_sources = 0

            totals = {
                "recipes": 0,
                "recipe_ingredients": 0,
                "recipe_instructions": 0,
                "canonical_links": 0,
                "ambiguous_ingredients": 0,
            }

            batch: List[ValidatedRecipeNLG] = []

            for line_num, row in self.source.open_csv_stream("full_dataset.csv"):
                if self.limit and accepted_recipes >= self.limit:
                    break
                total_rows += 1
                try:
                    rec = validate_recipe_record(row, line_num, seen_ids=seen_ids)
                    batch.append(rec)
                    accepted_recipes += 1

                    if rec.has_ner_failure:
                        ner_failures += 1
                    if rec.has_missing_directions:
                        missing_directions_recipes += 1
                    if rec.source_origin not in ("Gathered", "Recipes1M"):
                        unknown_sources += 1

                    if len(batch) >= self.batch_size:
                        b_counts = loader.load_recipes_batch(
                            recipes=batch,
                            canonical_map=canonical_map,
                            has_source_origin=has_source_origin,
                        )
                        for k, v in b_counts.items():
                            totals[k] += v
                        batch = []

                except DuplicateRecipeIDError as de:
                    rejected_rows += 1
                    duplicate_source_ids += 1
                    self._record_rejection(report, "full_dataset.csv", de.line_number, de.reason, row)
                except RecipeNLGValidationError as ve:
                    rejected_rows += 1
                    if ve.field_name == "title":
                        empty_titles += 1
                    elif ve.field_name == "ingredients":
                        missing_or_malformed_ingredients += 1
                    elif ve.field_name == "directions":
                        malformed_directions += 1
                    self._record_rejection(report, "full_dataset.csv", ve.line_number, ve.reason, row)

            if batch:
                b_counts = loader.load_recipes_batch(
                    recipes=batch,
                    canonical_map=canonical_map,
                    has_source_origin=has_source_origin,
                )
                for k, v in b_counts.items():
                    totals[k] += v

            # Record provenance
            size_bytes, sha256 = self.source.get_source_metadata()
            loader.record_provenance(
                source_url=self.meta.official_source_url,
                release_version="1.0.0",
                file_name="full_dataset.csv",
                sha256_checksum=sha256,
                total_rows=total_rows,
                imported_rows=accepted_recipes,
                rejected_rows=rejected_rows,
                notes=(
                    f"RecipeNLG Ingestion: {accepted_recipes:,} recipes, "
                    f"{totals['recipe_ingredients']:,} ingredients, "
                    f"{totals['recipe_instructions']:,} instructions."
                ),
            )

            conn.commit()

            report.metrics = {
                "total_source_rows": total_rows,
                "accepted_recipes": accepted_recipes,
                "rejected_rows": rejected_rows,
                "duplicate_source_ids": duplicate_source_ids,
                "empty_titles": empty_titles,
                "missing_or_malformed_ingredients": missing_or_malformed_ingredients,
                "malformed_directions": malformed_directions,
                "missing_directions_recipes": missing_directions_recipes,
                "ner_failures": ner_failures,
                "unknown_source_classifications": unknown_sources,
                "canonical_links": totals["canonical_links"],
                "ambiguous_ingredient_matches": totals["ambiguous_ingredients"],
                "recipe_ingredients_inserted": totals["recipe_ingredients"],
                "recipe_instructions_inserted": totals["recipe_instructions"],
            }

            # Update manifest
            record_ingestion_success(
                dataset_key="recipenlg",
                imported_counts={
                    "recipes": accepted_recipes,
                    "recipe_ingredients": totals["recipe_ingredients"],
                    "recipe_instructions": totals["recipe_instructions"],
                },
            )

    def _write_quality_report(self, report: RecipeNLGReport) -> None:
        """Serialize audit report to disk as JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORTS_DIR / f"recipenlg_ingestion_{timestamp}.json"
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2)
            report.report_file_path = str(report_path)
            logger.info(f"Audit report saved: {report_path}")
        except Exception as e:
            logger.error(f"Failed to write audit report to {report_path}: {e}")
