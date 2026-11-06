"""FoodFlow Ingestion Command-Line Interface (CLI)

Provides administrative commands for managing dataset ingestion:
  - doctor:  Comprehensive environment, dependency, and database health audit.
  - inspect: Inspect local CSV files, headers, file sizes, and optional row counts.
  - verify:  Verify file presence and SHA-256 checksums against the manifest.
  - status:  Display dataset availability, manifest state, and database connectivity.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ingestion.config import (
    DATASET_REGISTRY,
    DEFAULT_BATCH_SIZE,
    FOODCOM_RAW_DIR,
    PROCESSED_DATA_DIR,
    RECIPENLG_RAW_DIR,
    REPORTS_DIR,
    USDA_RAW_DIR,
    ensure_directories_exist,
    get_database_url,
    get_project_root,
    mask_database_url,
    resolve_dataset_key,
)
from ingestion.database import DatabaseConnectionError, check_health
from ingestion.datasets.foodcom.importer import FoodComImporter
from ingestion.datasets.foodcom.parser import FoodComParseError
from ingestion.datasets.recipenlg.importer import RecipeNLGImporter
from ingestion.datasets.recipenlg.parser import RecipeNLGParseError
from ingestion.datasets.usda.importer import USDAImporter
from ingestion.datasets.usda.parser import USDAParseError
from ingestion.logging_config import get_logger, setup_logging
from ingestion.manifest import (
    STATUS_COMPLETED,
    STATUS_DOWNLOADED,
    STATUS_FAILED,
    STATUS_NOT_DOWNLOADED,
    STATUS_VERIFIED,
    load_manifest,
    record_verified_file,
    save_manifest,
)
from ingestion.utils.checksums import compute_file_sha256, format_bytes, get_file_metadata
from ingestion.utils.csv_utils import count_csv_rows, inspect_csv_header
from ingestion.sampling import FoodComSampler, RecipeNLGSampler
from ingestion.taxonomy.seeder import TaxonomySeeder
from ingestion.taxonomy.validator import TaxonomyValidationError


logger = get_logger("cli")


# -----------------------------------------------------------------------------
# Formatting Helpers
# -----------------------------------------------------------------------------
def _header(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def _sub_header(title: str) -> None:
    print(f"\n--- {title} ---")


def _status_badge(passed: bool, label_pass: str = "PASS", label_fail: str = "FAIL") -> str:
    return f"[{label_pass}]" if passed else f"[{label_fail}]"


# -----------------------------------------------------------------------------
# Command 1: DOCTOR
# -----------------------------------------------------------------------------
def cmd_doctor(args: argparse.Namespace) -> int:
    """Check Python environment, directories, dependencies, and database health."""
    _header("FoodFlow Ingestion Environment Doctor")
    overall_ok = True

    # 1. Python Environment Check
    _sub_header("1. Python Environment")
    py_ver = sys.version_info
    py_str = f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"
    py_ok = (py_ver.major == 3 and py_ver.minor >= 11)
    if not py_ok:
        overall_ok = False
    print(f"{_status_badge(py_ok)} Python Version: {py_str} (Required: >= 3.11)")
    print(f"       Executable:     {sys.executable}")
    print(f"       Platform:       {sys.platform}")
    print(f"       Project Root:   {get_project_root()}")

    # 2. Directory Structure Check
    _sub_header("2. Data & Report Directories")
    ensure_directories_exist()
    dirs_to_check = [
        ("USDA Raw Data", USDA_RAW_DIR),
        ("Food.com Raw Data", FOODCOM_RAW_DIR),
        ("RecipeNLG Raw Data", RECIPENLG_RAW_DIR),
        ("Processed Output", PROCESSED_DATA_DIR),
        ("Audit Reports", REPORTS_DIR),
    ]
    dirs_ok = True
    for label, dir_path in dirs_to_check:
        exists = dir_path.exists() and dir_path.is_dir()
        if not exists:
            dirs_ok = False
        print(f"{_status_badge(exists)} {label:<22} : {dir_path}")

    # 3. Dependencies Check
    _sub_header("3. Python Dependencies")
    psycopg_ok = False
    try:
        import psycopg
        psycopg_ver = getattr(psycopg, "__version__", "installed")
        psycopg_ok = True
        print(f"{_status_badge(True)} psycopg 3 is installed (version: {psycopg_ver})")
    except ImportError:
        print(f"{_status_badge(False, 'PENDING', 'MISSING')} psycopg 3 is NOT installed.")
        print("       Run: pip install -r ingestion/requirements.txt")

    # 4. Environment Variables Check
    _sub_header("4. Environment Variables")
    db_url = get_database_url()
    if db_url:
        print(f"{_status_badge(True)} DATABASE_URL configured: {mask_database_url(db_url)}")
    else:
        print(f"{_status_badge(False, 'OPTIONAL', 'NOT SET')} DATABASE_URL is not set.")
        print("       Set DATABASE_URL to connect to PostgreSQL (e.g. postgresql://foodflow_admin:pw@localhost:5432/foodflow_db)")

    # 5. Database Health Check (if configured)
    _sub_header("5. Database Health & Schema Audit")
    db_connected = False
    if not db_url:
        print("[-] Database check skipped (DATABASE_URL not configured).")
    elif not psycopg_ok:
        print("[-] Database check skipped (psycopg dependency missing).")
    else:
        health = check_health(db_url)
        if health.is_connected:
            print(f"{_status_badge(True)} PostgreSQL Connection: Established")
            print(f"       Server Version:  {health.server_version.split(',')[0] if health.server_version else 'Unknown'}")
            print(f"       Connected User:  {health.connected_user}")
            print(f"       Database Name:   {health.database_name}")
            print("       Schema Audit:")
            for schema, present in (health.schemas_found or {}).items():
                print(f"         {_status_badge(present)} Schema '{schema}'")
            if health.all_schemas_present():
                db_connected = True
            else:
                print("       [!] Warning: One or more application schemas are missing. Run DDL scripts 001-004.")
        else:
            print(f"{_status_badge(False)} PostgreSQL Connection Failed")
            print(f"       Error: {health.error_message}")

    # 6. Manifest File Check
    _sub_header("6. Dataset Manifest Status")
    manifest = load_manifest()
    print(f"{_status_badge(True)} Manifest loaded: version {manifest.version}")
    print(f"       Tracked Datasets: {', '.join(manifest.datasets.keys())}")
    print(f"       Last Updated:     {manifest.last_updated}")

    # Summary
    _header("Doctor Audit Outcome")
    if not py_ok or not dirs_ok:
        print("[FAIL] Critical framework environment checks failed.\n")
        return 1

    if db_connected:
        print("[ONLINE & READY] Full environment (framework + live database) is operational.\n")
        return 0
    else:
        print("[FRAMEWORK READY (DATABASE OFFLINE)] Ingestion framework is ready for local file inspection and verification.")
        if not psycopg_ok:
            print("  - Optional database dependency 'psycopg' is missing (run: pip install -r ingestion/requirements.txt).")
        if not db_url:
            print("  - Database connection URL is not configured (set DATABASE_URL in environment).")
        print("  - Live database ingestion will be unavailable until database is configured.\n")
        return 0


# -----------------------------------------------------------------------------
# Command 2: INSPECT
# -----------------------------------------------------------------------------
def cmd_inspect(args: argparse.Namespace) -> int:
    """Inspect local dataset files, CSV headers, and optional row counts."""
    key = resolve_dataset_key(args.dataset)
    if not key:
        print(f"[ERROR] Unknown dataset: '{args.dataset}'. Choose from: usda, foodcom, recipenlg", file=sys.stderr)
        return 1

    meta = DATASET_REGISTRY[key]
    _header(f"Dataset Inspection: {meta.display_name}")
    print(f"Dataset Identifier : {meta.identifier}")
    print(f"Target Schema      : {meta.target_schema}")
    print(f"Official Source    : {meta.official_source_url}")
    print(f"Local Directory    : {meta.raw_directory}")
    print(f"License Terms      : {meta.license_terms}")
    print(f"Academic Citation  : {meta.reference_citation}")

    _sub_header("File Inventory & Header Inspection")
    missing_files: List[str] = []

    for file_name in meta.expected_files:
        file_path = meta.raw_directory / file_name
        print(f"\nFile: {file_name}")
        if not file_path.exists():
            print("  Status   : [MISSING]")
            missing_files.append(file_name)
            continue

        # File is present on disk
        size_bytes = file_path.stat().st_size
        print(f"  Status   : [PRESENT]")
        print(f"  Size     : {size_bytes:,} bytes ({format_bytes(size_bytes)})")

        # Header inspection (streaming line 1 only)
        try:
            headers = inspect_csv_header(file_path)
            print(f"  Columns  : ({len(headers)} fields) {headers[:8]}")
            if len(headers) > 8:
                print(f"             ... and {len(headers) - 8} more columns")
        except Exception as e:
            print(f"  Columns  : [ERROR reading CSV header: {e}]")

        # Optional row count
        if args.count_rows:
            print("  Row Count: Counting rows (streaming line break scan)...", end="", flush=True)
            try:
                row_count = count_csv_rows(file_path, has_header=True)
                print(f"\r  Row Count: {row_count:,} data rows")
            except Exception as e:
                print(f"\r  Row Count: [ERROR: {e}]")
        else:
            print("  Row Count: (Row count skipped. Pass --count-rows to calculate)")

    if missing_files:
        _sub_header("Action Required: Missing Files")
        print(f"[!] The following expected files are missing in '{meta.raw_directory}':")
        for mf in missing_files:
            print(f"    - {mf}")
        print("\nDownload Instructions:")
        print(f"  1. Visit the official dataset portal: {meta.official_source_url}")
        print(f"  2. Download the required archive/files.")
        print(f"  3. Place uncompressed CSV files into: {meta.raw_directory}")
        print(f"  4. Re-run 'python -m ingestion.cli inspect --dataset {args.dataset}'")
        return 1

    print("\n[PASS] All expected files are present locally and headers parsed successfully.\n")
    return 0


# -----------------------------------------------------------------------------
# Command 3: VERIFY
# -----------------------------------------------------------------------------
def cmd_verify(args: argparse.Namespace) -> int:
    """Verify local dataset files and SHA-256 checksums against the manifest."""
    datasets_to_verify = (
        list(DATASET_REGISTRY.keys())
        if args.dataset in ("all", None)
        else [resolve_dataset_key(args.dataset)]
    )

    if not datasets_to_verify or None in datasets_to_verify:
        print(f"[ERROR] Unknown dataset: '{args.dataset}'. Choose from: usda, foodcom, recipenlg, all", file=sys.stderr)
        return 1

    _header("FoodFlow Dataset File & Checksum Verification")
    manifest = load_manifest()
    total_files = 0
    verified_files = 0
    missing_files = 0
    mismatched_files = 0

    for key in datasets_to_verify:
        meta = DATASET_REGISTRY[key]
        entry = manifest.datasets[key]
        _sub_header(f"{meta.display_name} ({key})")

        for file_name in meta.expected_files:
            total_files += 1
            file_path = meta.raw_directory / file_name
            print(f"File: {file_name}")

            if not file_path.exists():
                print(f"  Status   : [MISSING] File does not exist at {file_path}")
                missing_files += 1
                continue

            # Calculate genuine streaming SHA-256
            size_bytes = file_path.stat().st_size
            print(f"  Size     : {size_bytes:,} bytes ({format_bytes(size_bytes)})")
            print("  SHA-256  : Computing streaming SHA-256 hash...", end="", flush=True)
            sha256 = compute_file_sha256(file_path)
            print(f"\r  SHA-256  : {sha256}")

            # Manifest comparison
            manifest_rec = entry.files.get(file_name)
            if manifest_rec and manifest_rec.sha256_checksum:
                expected_sha = manifest_rec.sha256_checksum
                if sha256.lower() == expected_sha.lower():
                    print("  Match    : [VERIFIED] Checksum matches manifest record.")
                    verified_files += 1
                else:
                    print(f"  Match    : [MISMATCH] Expected {expected_sha}, got {sha256}")
                    mismatched_files += 1
            else:
                print("  Manifest : Recorded new verified metadata in manifest.")
                # Record verified file
                last_mod = datetime.fromtimestamp(
                    file_path.stat().st_mtime, timezone.utc
                ).isoformat()
                record_verified_file(
                    dataset_key=key,
                    file_name=file_name,
                    size_bytes=size_bytes,
                    sha256_checksum=sha256,
                    last_modified=last_mod,
                )
                verified_files += 1

    _header("Verification Summary")
    print(f"Total Expected Files : {total_files}")
    print(f"Verified Files       : {verified_files}")
    print(f"Missing Files        : {missing_files}")
    print(f"Mismatched Files     : {mismatched_files}")

    if missing_files > 0:
        print("\n[NOTE] Some files have not been downloaded yet. Run 'inspect' for download links.")
        return 0  # Informational outcome
    if mismatched_files > 0:
        print("\n[FAIL] File checksum mismatch detected! Check local archives.")
        return 1

    print("\n[PASS] All local dataset files verified successfully.\n")
    return 0


# -----------------------------------------------------------------------------
# Command 4: STATUS
# -----------------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> int:
    """Display overall dataset availability, manifest state, and DB connectivity."""
    _header("FoodFlow Dataset Ingestion Framework Status")

    manifest = load_manifest()
    db_url = get_database_url()

    # Database connectivity snapshot
    _sub_header("Database Connectivity")
    if db_url:
        health = check_health(db_url)
        if health.is_connected:
            print(f"Status   : [ONLINE] Connected to '{health.database_name}' as '{health.connected_user}'")
            print(f"Engine   : {health.server_version.split(',')[0] if health.server_version else 'PostgreSQL 16'}")
            print(f"Schemas  : profile_nutrition={health.schemas_found.get('profile_nutrition')}, "
                  f"recipe_catalog={health.schemas_found.get('recipe_catalog')}, "
                  f"meal_planner={health.schemas_found.get('meal_planner')}")
        else:
            print(f"Status   : [OFFLINE] {health.error_message}")
    else:
        print("Status   : [NOT CONFIGURED] DATABASE_URL is not set.")

    # Dataset Status Table
    _sub_header("Dataset Sources & Manifest State")
    print(f"{'Dataset':<10} | {'Schema':<18} | {'Status':<16} | {'Files Present':<14} | {'Imported Records'}")
    print("-" * 80)

    for key, meta in DATASET_REGISTRY.items():
        entry = manifest.datasets[key]
        # Count files on disk
        present_count = sum(
            1 for fn in meta.expected_files if (meta.raw_directory / fn).exists()
        )
        files_str = f"{present_count} / {len(meta.expected_files)}"

        imported_total = sum(entry.imported_row_counts.values()) if entry.imported_row_counts else 0
        imported_str = f"{imported_total:,}" if imported_total > 0 else "None (Pending)"

        print(
            f"{key:<10} | {meta.target_schema:<18} | {entry.import_status:<16} | {files_str:<14} | {imported_str}"
        )

    print("-" * 80)
    print("Statuses: not_downloaded -> downloaded -> verified -> partially_imported -> completed\n")
    return 0


# -----------------------------------------------------------------------------
# Command 5: INGEST-USDA
# -----------------------------------------------------------------------------
def cmd_ingest_usda(args: argparse.Namespace) -> int:
    """Execute USDA FoodData Central ingestion for Foundation Foods or SR Legacy."""
    _header("FoodFlow USDA FoodData Central Ingestion")
    source_path = Path(args.source)
    if not source_path.exists():
        print(f"[ERROR] Specified USDA source path does not exist: {source_path}", file=sys.stderr)
        return 1

    try:
        importer = USDAImporter(
            source_path=source_path,
            collection_type=args.data_type,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            limit=args.limit,
        )
        report = importer.run()

        _header("USDA Ingestion Summary")
        print(f"Collection       : {report.display_name} ({report.collection_id})")
        print(f"Source Path      : {report.source_path}")
        print(f"Execution Mode   : {'DRY-RUN (No database writes)' if report.dry_run else 'LIVE INGESTION'}")
        print(f"Outcome Status   : {report.status.upper()}")
        print("\nRecord Counts:")
        for tbl, count in report.imported_counts.items():
            print(f"  - {tbl:<25} : {count:,} records processed/accepted")
        if report.rejected_counts:
            print("\nRejected Rows:")
            for fn, rej_count in report.rejected_counts.items():
                if rej_count > 0:
                    print(f"  - {fn:<25} : {rej_count:,} rows rejected")
        if report.sample_rejections:
            print("\nSample Rejection Details:")
            for rej in report.sample_rejections[:5]:
                print(f"  [{rej['file']}:{rej['line']}] {rej['reason']}")

        status_flag = "PASS" if "passed" in report.status or report.status == "completed" else "FAIL"
        print(f"\n[{status_flag}] USDA ingestion finished.\n")
        return 0
    except DatabaseConnectionError as dbe:
        print(f"\n[ERROR] Database Configuration Error: {dbe}", file=sys.stderr)
        return 1
    except USDAParseError as pe:
        print(f"\n[ERROR] Archive / Header Validation Error: {pe}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] Ingestion Failed: {e}", file=sys.stderr)
        return 1


# -----------------------------------------------------------------------------
# Command 6: INGEST-FOODCOM
# -----------------------------------------------------------------------------
def cmd_ingest_foodcom(args: argparse.Namespace) -> int:
    """Ingest Food.com recipes and interaction ratings into recipe_catalog schema."""
    _header("FoodFlow Food.com Recipe & Interaction Ingestion")
    source_path = Path(args.source).resolve()
    if not source_path.exists():
        print(f"[FAIL] Specified source path does not exist: {source_path}", file=sys.stderr)
        return 1

    try:
        importer = FoodComImporter(
            source_path=source_path,
            component=args.component,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            limit_recipes=args.limit_recipes,
            limit_interactions=args.limit_interactions,
        )
        report = importer.run()

        _header("Food.com Ingestion Summary")
        print(f"Component        : {report.component.upper()}")
        print(f"Source Path      : {report.source_path}")
        print(f"Execution Mode   : {'DRY-RUN (No database writes)' if report.dry_run else 'LIVE INGESTION'}")
        print(f"Outcome Status   : {report.status.upper()}")

        if report.recipe_metrics:
            print("\nRecipe Metrics:")
            for k, v in report.recipe_metrics.items():
                val_str = f"{v:,}" if isinstance(v, (int, float)) else str(v)
                print(f"  - {k:<30} : {val_str}")

        if report.interaction_metrics:
            print("\nInteraction Metrics:")
            for k, v in report.interaction_metrics.items():
                val_str = f"{v:,}" if isinstance(v, (int, float)) else str(v)
                print(f"  - {k:<30} : {val_str}")

        if report.sample_rejections:
            print("\nSample Rejection Details:")
            for rej in report.sample_rejections[:5]:
                print(f"  [{rej.get('file', 'unknown')}:{rej.get('line', '?')}] {rej.get('reason', '')}")

        if report.report_file_path:
            print(f"\nAudit Report     : {report.report_file_path}")

        status_flag = "PASS" if "passed" in report.status or report.status in ("completed", "partially_imported") else "FAIL"
        print(f"\n[{status_flag}] Food.com ingestion finished.\n")
        return 0
    except DatabaseConnectionError as dbe:
        print(f"\n[ERROR] Database Configuration Error: {dbe}", file=sys.stderr)
        return 1
    except FoodComParseError as pe:
        print(f"\n[ERROR] Archive / Header Validation Error: {pe}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] Ingestion Failed: {e}", file=sys.stderr)
        return 1


# -----------------------------------------------------------------------------
# Command 7: INGEST-RECIPENLG
# -----------------------------------------------------------------------------
def cmd_ingest_recipenlg(args: argparse.Namespace) -> int:
    """Ingest RecipeNLG recipe corpus into recipe_catalog schema."""
    _header("FoodFlow RecipeNLG Large Scale Recipe Corpus Ingestion")
    source_path = Path(args.source).resolve()
    if not source_path.exists():
        print(f"[FAIL] Specified source path does not exist: {source_path}", file=sys.stderr)
        return 1

    try:
        importer = RecipeNLGImporter(
            source_path=source_path,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            limit=args.limit,
            force=args.force,
        )
        report = importer.run()

        _header("RecipeNLG Ingestion Summary")
        print(f"Source Path      : {report.source_path}")
        print(f"Execution Mode   : {'DRY-RUN (No database writes)' if report.dry_run else 'LIVE INGESTION'}")
        print(f"Outcome Status   : {report.status.upper()}")

        if report.metrics:
            print("\nIngestion Metrics:")
            for k, v in report.metrics.items():
                val_str = f"{v:,}" if isinstance(v, (int, float)) else str(v)
                print(f"  - {k:<34} : {val_str}")

        if report.sample_rejections:
            print("\nSample Rejection Details:")
            for rej in report.sample_rejections[:5]:
                print(f"  [{rej.get('file', 'unknown')}:{rej.get('line', '?')}] {rej.get('reason', '')}")

        if report.report_file_path:
            print(f"\nAudit Report     : {report.report_file_path}")

        status_flag = "PASS" if "passed" in report.status or report.status == "completed" else "FAIL"
        print(f"\n[{status_flag}] RecipeNLG ingestion finished.\n")
        return 0
    except DatabaseConnectionError as dbe:
        print(f"\n[ERROR] Database Configuration Error: {dbe}", file=sys.stderr)
        return 1
    except RecipeNLGParseError as pe:
        print(f"\n[ERROR] Archive / Header Validation Error: {pe}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] Ingestion Failed: {e}", file=sys.stderr)
        return 1


def cmd_sample(args: argparse.Namespace) -> int:
    """Execute stratified development sampling for Food.com or RecipeNLG."""
    key = resolve_dataset_key(args.dataset)
    if key not in ("foodcom", "recipenlg"):
        print(
            f"\n[ERROR] Stratified sampling is supported for 'foodcom' and 'recipenlg'. Got '{args.dataset}'.",
            file=sys.stderr,
        )
        print("Note: USDA reference data is ingested directly and not randomly sampled.", file=sys.stderr)
        return 1

    source_path = Path(args.source).resolve()
    if not source_path.exists():
        print(f"\n[ERROR] Source path does not exist: {source_path}", file=sys.stderr)
        return 1

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else (PROCESSED_DATA_DIR / "dev_sample" / key).resolve()
    )

    try:
        if key == "foodcom":
            sampler = FoodComSampler(
                source_path=source_path,
                output_dir=output_dir,
                limit=args.limit,
                seed=args.seed,
            )
        else:
            sampler = RecipeNLGSampler(
                source_path=source_path,
                output_dir=output_dir,
                limit=args.limit,
                seed=args.seed,
            )

        report = sampler.run(dry_run=args.dry_run)
        report.print_summary()
        return 0
    except Exception as e:
        print(f"\n[ERROR] Sampling Failed: {e}", file=sys.stderr)
        return 1


def cmd_seed_ingredient_taxonomy(args: argparse.Namespace) -> int:
    """Validate canonical taxonomy seed, generate reports, and link recipe ingredients."""
    source_dir = Path(args.source).resolve()
    print("=" * 80)
    print("FoodFlow Canonical Ingredient Taxonomy Seeder & Recipe Linking")
    print("=" * 80)
    print(f"Source Audit Directory: {source_dir}")
    print(f"Execution Mode:         {'DRY RUN (simulation only)' if args.dry_run else 'LIVE APPLY (modifies database)'}")

    try:
        seeder = TaxonomySeeder(source_audit_dir=source_dir)
        print("\n1. Validating canonical seed definitions...")
        seeder.validate()
        print("   [OK] Canonical definitions, categories, and synonym constraints valid.")

        print("\n2. Generating reviewable audit artifacts...")
        artifacts = seeder.generate_seed_artifacts(output_dir=source_dir)
        for name, path in artifacts.items():
            print(f"   [OK] {name}: {path}")

        print(f"\n3. Executing {'dry-run simulation' if args.dry_run else 'database population and linking'}...")
        stats = seeder.seed(dry_run=args.dry_run)

        print("\n" + "=" * 80)
        print("Taxonomy Seeding & Ingredient Linking Summary")
        print("=" * 80)
        print(f"Mode:                                {stats['mode'].upper()}")
        print(f"Seed Version:                        {stats['seed_version']}")
        print(f"Canonical Ingredients Seeded:        {stats['canonical_inserted']:,}")
        print(f"Approved Synonyms Seeded:            {stats['synonyms_inserted']:,}")
        print(f"Recipe Ingredients Linked:           {stats['recipe_ingredients_linked']:,}")
        print(f"Recipe Ingredients Remaining NULL:   {stats['recipe_ingredients_remaining_null']:,}")
        print(f"Total Recipe Ingredients:            {stats['total_recipe_ingredients']:,}")
        pct_linked = (
            (stats['recipe_ingredients_linked'] / stats['total_recipe_ingredients'] * 100)
            if stats['total_recipe_ingredients'] > 0 else 0.0
        )
        print(f"Coverage of Linked Ingredients:      {pct_linked:.2f}%")
        print(f"Elapsed Time:                        {stats['elapsed_seconds']}s")
        print("=" * 80)

        if args.dry_run:
            print("\n[INFO] Dry run completed successfully. No changes were committed to the database.")
        else:
            print("\n[SUCCESS] Live seeding and recipe ingredient linking committed successfully.")
        return 0

    except TaxonomyValidationError as e:
        print(f"\n[ERROR] Taxonomy Validation Failed: {e}", file=sys.stderr)
        return 1
    except DatabaseConnectionError as e:
        print(f"\n[ERROR] Database Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n[ERROR] Seeding Failed: {e}", file=sys.stderr)
        return 1


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser for the ingestion CLI."""
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.cli",
        description="FoodFlow Dataset Ingestion & Seeding Infrastructure CLI (Phase 1, Step 03.5)",
        epilog="Academic non-commercial educational use only. Respects USDA, Food.com, and RecipeNLG licenses.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. doctor
    subparsers.add_parser(
        "doctor",
        help="Check Python environment, directory tree, dependencies, and PostgreSQL health.",
    )

    # 2. inspect
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect local dataset files, CSV headers, file sizes, and optional row counts.",
    )
    inspect_parser.add_argument(
        "--dataset",
        "-d",
        required=True,
        choices=["usda", "foodcom", "recipenlg", "usda_fdc", "food_com"],
        help="Target dataset to inspect.",
    )
    inspect_parser.add_argument(
        "--count-rows",
        action="store_true",
        default=False,
        help="Calculate streaming row count. (Omitted by default for performance on large files).",
    )

    # 3. verify
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify file existence and SHA-256 checksums against the manifest.",
    )
    verify_parser.add_argument(
        "--dataset",
        "-d",
        default="all",
        choices=["usda", "foodcom", "recipenlg", "all"],
        help="Dataset to verify (default: all).",
    )

    # 4. status
    subparsers.add_parser(
        "status",
        help="Display dataset availability, manifest state, and database connectivity.",
    )

    # 5. ingest-usda
    usda_parser = subparsers.add_parser(
        "ingest-usda",
        help="Ingest USDA FoodData Central dataset (Foundation Foods or SR Legacy) into profile_nutrition.",
    )
    usda_parser.add_argument(
        "--data-type",
        "-t",
        required=True,
        choices=["foundation", "sr-legacy", "sr_legacy"],
        help="Target USDA collection type ('foundation' or 'sr-legacy').",
    )
    usda_parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="Path to USDA ZIP archive file or extracted directory.",
    )
    usda_parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of records per SQL batch insert (default: {DEFAULT_BATCH_SIZE}).",
    )
    usda_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate and parse records without modifying PostgreSQL or manifest.",
    )
    usda_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Optional upper limit on food items to ingest (for testing/development).",
    )

    # 6. ingest-foodcom
    foodcom_parser = subparsers.add_parser(
        "ingest-foodcom",
        help="Ingest Food.com recipes and interaction ratings into recipe_catalog.",
    )
    foodcom_parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="Path to Food.com directory or ZIP archive containing RAW_recipes.csv / RAW_interactions.csv.",
    )
    foodcom_parser.add_argument(
        "--component",
        "-c",
        choices=["all", "recipes", "interactions"],
        default="all",
        help="Which component to ingest: recipes, interactions, or all (default: all).",
    )
    foodcom_parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of records per SQL batch insert (default: {DEFAULT_BATCH_SIZE}).",
    )
    foodcom_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate and parse records without modifying PostgreSQL or manifest.",
    )
    foodcom_parser.add_argument(
        "--limit-recipes",
        type=int,
        default=None,
        help="Optional upper limit on recipes to ingest (for testing/development).",
    )
    foodcom_parser.add_argument(
        "--limit-interactions",
        type=int,
        default=None,
        help="Optional upper limit on interactions to ingest (for testing/development).",
    )

    # 7. ingest-recipenlg
    recipenlg_parser = subparsers.add_parser(
        "ingest-recipenlg",
        help="Ingest RecipeNLG recipe corpus into recipe_catalog.",
    )
    recipenlg_parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="Path to RecipeNLG CSV file, ZIP archive, or directory containing full_dataset.csv.",
    )
    recipenlg_parser.add_argument(
        "--batch-size",
        "-b",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of records per SQL batch insert (default: {DEFAULT_BATCH_SIZE}).",
    )
    recipenlg_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate and parse records without modifying PostgreSQL or manifest.",
    )
    recipenlg_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Optional upper limit on recipes to ingest (for testing/development).",
    )
    recipenlg_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force ingestion even if additive migration column (source_origin) is absent.",
    )


    # 8. sample
    sample_parser = subparsers.add_parser(
        "sample",
        help="Generate stratified development sample subsets (Food.com and RecipeNLG).",
    )
    sample_parser.add_argument(
        "--dataset",
        "-d",
        required=True,
        choices=["foodcom", "recipenlg", "food_com", "recipe_nlg"],
        help="Target dataset to sample ('foodcom' or 'recipenlg').",
    )
    sample_parser.add_argument(
        "--source",
        "-s",
        required=True,
        help="Path to dataset file, directory, or ZIP archive.",
    )
    sample_parser.add_argument(
        "--output-dir",
        "-o",
        default=None,
        help="Directory to write sampled CSV files and audit report (default: data/processed/dev_sample/<dataset>).",
    )
    sample_parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=25000,
        help="Target sample size (number of recipes, default: 25000).",
    )
    sample_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic random seed (default: 42).",
    )
    sample_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Execute stratum profiling and quota allocation without writing output files.",
    )

    # 9. seed-ingredient-taxonomy
    seed_parser = subparsers.add_parser(
        "seed-ingredient-taxonomy",
        help="Validate canonical taxonomy seed, generate reports, and link recipe ingredients.",
    )
    seed_parser.add_argument(
        "--source",
        "-s",
        default="data/processed/reports/ingredient_taxonomy_audit",
        help="Directory containing Step 04.5B-1 ingredient audit artifacts (default: data/processed/reports/ingredient_taxonomy_audit).",
    )
    seed_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate definitions, preview linking, and simulate seeding without committing changes.",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI execution entrypoint."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "inspect":
        return cmd_inspect(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "ingest-usda":
        return cmd_ingest_usda(args)
    elif args.command == "ingest-foodcom":
        return cmd_ingest_foodcom(args)
    elif args.command == "ingest-recipenlg":
        return cmd_ingest_recipenlg(args)
    elif args.command == "sample":
        return cmd_sample(args)
    elif args.command == "seed-ingredient-taxonomy":
        return cmd_seed_ingredient_taxonomy(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())

