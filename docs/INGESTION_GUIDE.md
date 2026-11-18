# NutriPod — Dataset Ingestion Framework Guide

| Metadata | Details |
| :--- | :--- |
| **Framework Version** | 1.3.0 (Phase 1, Step 03.4 RecipeNLG Importer) |
| **Target Engine** | PostgreSQL 16 (`profile_nutrition` & `recipe_catalog` schemas) |
| **Python Version** | Python 3.11+ (Host: Python 3.13) |
| **CLI Entrypoint** | `python -m ingestion.cli <command>` |
| **Manifest Path** | `data/manifest.json` |

---

## 1. Overview & Architecture Boundary

The NutriPod Ingestion Framework is a **reproducible, standalone data engineering CLI and utility package**. It is designed to stream, validate, sample, and seed three large external research and reference datasets into PostgreSQL 16.

> [!IMPORTANT]
> **Boundary Rule**: The ingestion pipeline is **infrastructure code**, **NOT** a fourth backend microservice. It does not run as a persistent daemon or expose REST endpoints. It operates as an administrative batch ETL tool executed by developers or CI pipelines before service startup.

```
+───────────────────────────────────────────────────────────────────────────────────+
|                     STANDALONE INGESTION CLI (python -m ingestion.cli)            |
|                     [doctor | inspect | verify | status | (future: seed)]         |
+───────────────────────────────────────────────────────────────────────────────────+
        │                                  │                                  │
        ▼                                  ▼                                  ▼
+──────────────────────────+   +──────────────────────────+   +──────────────────────────+
|  USDA FoodData Central   |   |   Food.com Recipes       |   |       RecipeNLG          |
|  data/raw/usda/          |   |   data/raw/foodcom/      |   |   data/raw/recipenlg/    |
|  • food.csv              |   |   • RAW_recipes.csv      |   |   • full_dataset.csv     |
|  • nutrient.csv          |   |   • RAW_interactions.csv |   |   (~2.23M records)       |
|  • food_nutrient.csv     |   |   (231k recipes)         |   |   (1.8 GB CSV)           |
|  • food_portion.csv      |   +──────────────────────────+   +──────────────────────────+
+──────────────────────────+                 │                              │
        │                                    └──────────────┬───────────────┘
        ▼                                                   ▼
+──────────────────────────+               +─────────────────────────────────+
| SCHEMA: profile_nutrition|               |      SCHEMA: recipe_catalog     |
| (Target: Member 1, :8001)|               |      (Target: Member 2, :8002)  |
+──────────────────────────+               +─────────────────────────────────+
| • usda_foods             |               | • canonical_ingredients         |
| • usda_nutrients         |               | • ingredient_synonyms           |
| • usda_food_nutrients    |               | • recipes                       |
| • usda_food_portions     |               | • recipe_ingredients            |
| • ingestion_provenance   |               | • recipe_instructions           |
|                          |               | • recipe_tags                   |
|                          |               | • recipe_ratings                |
|                          |               | • recipe_nutrition_raw          |
|                          |               | • ingestion_provenance          |
+──────────────────────────+               +─────────────────────────────────+
```

---

## 2. Directory Structure & Layout

```
FoodFlow/
├── data/
│   ├── manifest.json              # Structured provenance and audit manifest (tracked in Git)
│   ├── raw/                       # Raw downloaded archives (gitignored)
│   │   ├── usda/                  # USDA FDC CSVs (food.csv, nutrient.csv, etc.)
│   │   ├── foodcom/               # Food.com CSVs (RAW_recipes.csv, RAW_interactions.csv)
│   │   └── recipenlg/             # RecipeNLG CSV (full_dataset.csv)
│   ├── processed/                 # Intermediate sanitized/stratified files (gitignored)
│   └── reports/                   # Execution logs and validation reports (gitignored)
├── ingestion/
│   ├── __init__.py                # Package declaration
│   ├── cli.py                     # Unified CLI entrypoint (argparse)
│   ├── config.py                  # Directory paths, dataset registry, URL masking
│   ├── database.py                # PostgreSQL 16 connectivity (psycopg 3, context managers)
│   ├── manifest.py                # Audit manifest parser and state transitions
│   ├── logging_config.py          # Formatted stdout and persistent report logging
│   ├── requirements.txt           # Minimal dependency declaration (psycopg[binary])
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── checksums.py           # Chunked streaming SHA-256 calculation
│   │   └── csv_utils.py           # Streaming CSV reader, header parser, batch iterator
│   ├── datasets/                  # Dataset-specific importers (modular structure)
│   │   ├── __init__.py
│   │   ├── usda/                  # USDA pipeline (Step 03.2)
│   │   ├── foodcom/               # Food.com pipeline (Step 03.3)
│   │   └── recipenlg/             # RecipeNLG pipeline (Step 03.4)
│   └── sampling/                  # Stratified sampling engine (Step 03.5 placeholder)
└── tests/
    └── ingestion/                 # 76 unittest test cases (standard library)
```

---

## 3. Python Environment & Setup

NutriPod supports **Python 3.11+** (verified on host **Python 3.13**). The framework deliberately avoids heavy data libraries like pandas or NumPy, utilizing Python's built-in standard library (`csv`, `hashlib`, `json`, `argparse`, `dataclasses`, `logging`) for bounded memory usage and maximum portability.

### 3.1 Creating a Virtual Environment
```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3.2 Installing Ingestion Dependencies
```powershell
pip install -r ingestion/requirements.txt
```
*Note*: `ingestion/requirements.txt` specifies only `psycopg[binary]>=3.1.18` for database connectivity. Standard inspection, verification, and manifest commands operate without third-party dependencies.

### 3.3 Environment Variables
Configure the connection string in your environment or terminal session:
```powershell
# Windows PowerShell
$env:DATABASE_URL="postgresql://foodflow_admin:CHANGE_ME@localhost:5432/foodflow_db"
$env:FOODFLOW_BATCH_SIZE="1000"

# Linux / macOS
export DATABASE_URL="postgresql://foodflow_admin:CHANGE_ME@localhost:5432/foodflow_db"
export FOODFLOW_BATCH_SIZE="1000"
```

---

## 4. CLI Usage & Commands

The ingestion CLI is accessed via `python -m ingestion.cli <command>`.

### 4.1 `doctor`
Performs an automated pre-flight audit of the Python environment, directory tree, dependencies, environment variables, and PostgreSQL schema readiness.
```powershell
python -m ingestion.cli doctor
```
*Output checks*:
1. Python version ($\ge 3.11$).
2. Existence of `data/raw/*`, `data/processed/`, `data/reports/`.
3. Availability of `psycopg` 3.
4. Masked validation of `DATABASE_URL`.
5. Read-only probe of `information_schema.schemata` for `profile_nutrition`, `recipe_catalog`, and `meal_planner`.
6. Manifest integrity.

### 4.2 `inspect`
Inspects local CSV files without reading entire files into memory. Verifies existence, file sizes, and parses CSV column headers. Full row counting is an optional flag (`--count-rows`) to prevent multi-second delays on multi-million row files (such as RecipeNLG).
```powershell
# Quick inspection of headers and file sizes
python -m ingestion.cli inspect --dataset usda
python -m ingestion.cli inspect --dataset foodcom
python -m ingestion.cli inspect --dataset recipenlg

# Deep inspection with streaming row counting
python -m ingestion.cli inspect --dataset foodcom --count-rows
```
*Error Handling*: If any expected file is missing, `inspect` returns exit code 1 with exact download instructions and destination paths.

### 4.3 `verify`
Computes streaming SHA-256 hashes of local dataset files in 1 MB chunks and verifies them against the manifest.
```powershell
# Verify all datasets
python -m ingestion.cli verify

# Verify a single dataset
python -m ingestion.cli verify --dataset foodcom
```
*Integrity Rule*: Verified hashes and file sizes are recorded in `data/manifest.json`. Never invent checksums.

### 4.4 `status`
Displays a comprehensive tabular dashboard of dataset availability, manifest state, imported row counts, and database connection status.
```powershell
python -m ingestion.cli status
```

### 4.5 `ingest-usda`
Ingests USDA FoodData Central Foundation Foods or SR Legacy into PostgreSQL 16 `profile_nutrition` schema.
```powershell
# Dry-run validation (no database writes)
python -m ingestion.cli ingest-usda --data-type foundation --source data/raw/usda/foundation --dry-run

# Live ingestion (requires DATABASE_URL with foodflow_admin role)
python -m ingestion.cli ingest-usda --data-type foundation --source data/raw/usda/foundation --batch-size 1000

# SR Legacy ingestion from ZIP archive
python -m ingestion.cli ingest-usda --data-type sr-legacy --source data/raw/usda/sr_legacy.zip --batch-size 1000
```
*Full Guide*: See [`docs/USDA_INGESTION.md`](USDA_INGESTION.md) for detailed field mapping and collection handling.

### 4.6 `ingest-foodcom`
Ingests Food.com recipes and historical interaction ratings into PostgreSQL 16 `recipe_catalog` schema.
```powershell
# Dry-run validation (no database writes)
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --dry-run

# Full live ingestion (recipes and interactions)
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/

# Ingest recipes only (sets manifest to partially_imported)
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --component recipes

# Ingest interactions ratings only (requires recipes previously ingested)
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --component interactions

# Development limit testing with custom batch size
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --limit-recipes 1000 --limit-interactions 5000 --batch-size 500 --dry-run
```
*Full Guide*: See [`docs/FOODCOM_INGESTION.md`](FOODCOM_INGESTION.md) for detailed field mapping, %DV semantics, and ratings aggregation architecture.

### 4.7 `ingest-recipenlg`
Ingests RecipeNLG large-scale recipe corpus (~2.23M recipes) into PostgreSQL 16 `recipe_catalog` schema.
```powershell
# Dry-run validation (no database writes)
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/full_dataset.csv --dry-run

# Dry-run on sample of 1,000 recipes
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/full_dataset.csv --limit 1000 --dry-run

# Live ingestion (requires database/migrations/005_add_recipenlg_source_origin.sql applied)
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/full_dataset.csv --batch-size 1000

# Direct ZIP archive streaming without extraction
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/recipenlg.zip --batch-size 1000
```
*Full Guide*: See [`docs/RECIPENLG_INGESTION.md`](RECIPENLG_INGESTION.md) for detailed field mapping, conservative quantity parsing, and canonical entity linking.

---

## 5. Dataset Manifest Architecture (`data/manifest.json`)

The manifest acts as the persistent source of truth for dataset tracking:
- **Zero Fabrication**: Initial manifests declare `not_downloaded` status with `null` for download dates, row counts, and checksums. Metadata is updated **only** upon successful local operations.
- **Audit Fields**:
  - `official_source_url`: Verifiable upstream URL.
  - `license_notes` & `reference_citation`: Educational / non-commercial legal terms.
  - `expected_files`: Canonical filenames required by the importer.
  - `import_status`: State transitions:
    $$\text{not\_downloaded} \longrightarrow \text{downloaded} \longrightarrow \text{verified} \longrightarrow \text{partially\_imported} \longrightarrow \text{completed}$$
    $$\text{any state} \xrightarrow{\text{on exception}} \text{failed}$$
  - `imported_row_counts`: Exact row counts loaded into PostgreSQL tables.
  - `failure_record`: Step name, error message, and ISO timestamp if an error occurs.

---

## 6. Large Dataset & Streaming Architecture

RecipeNLG contains ~2.23 million records (~1.8 GB CSV), and Food.com contains ~231k recipes and over 1 million ratings. Loading these files entirely into memory will exhaust student RAM.

### 6.1 Memory-Bounded Streaming
- **Chunked File Hashing**: `compute_file_sha256()` reads binary chunks of 1 MB, keeping memory overhead under 10 MB regardless of file size.
- **Streaming Dict Reader**: `stream_csv_dict()` lazily yields one row at a time. Peak memory usage per process is $O(1)$ row.
- **Configurable Batching**: `batch_iterator()` groups rows into slices of `batch_size` (default: 1,000) for PostgreSQL batch inserts.
- **CSV Field Size Limit**: Windows and Unix systems differ in default CSV field limits. `csv.field_size_limit(2147483647)` is set automatically on import to handle recipes with dozens of steps without crashing.

### 6.2 Malformed Row Accounting
The framework never silently drops bad records. The `IngestionProgressTracker` tracks:
- `total_read`: Total CSV rows processed.
- `accepted`: Valid records staged for insertion.
- `rejected`: Malformed rows skipped, logged with 1-based CSV line numbers, failure reasons, and raw sample snippets.

---

## 7. Database Access & Role Rules

- **Administrative Role Required**: Ingestion operations insert data into both `profile_nutrition` (USDA) and `recipe_catalog` (Food.com, RecipeNLG). Application service roles (`foodflow_profile_user`, `foodflow_recipe_user`, `foodflow_planner_user`) are strictly isolated to single schemas and **cannot** perform cross-schema ingestion.
- **Ingestion Identity**: Connect using the migration role `foodflow_admin` (or superuser `postgres`).
- **Connection URL**:
  ```
  postgresql://foodflow_admin:CHANGE_ME@localhost:5432/foodflow_db
  ```
- **Transaction Safety**: Context managers (`get_connection()`) enforce explicit transaction boundaries. If a batch fails, the transaction is automatically rolled back, and the failure is recorded in the manifest.

---

## 8. Data Hygiene & Version Control Rules

1. **Raw Files Never Committed**: `.gitignore` strictly ignores `data/raw/*`, `data/processed/*`, and `data/reports/*`.
2. **Directory Structure Preserved**: Empty directories are tracked in Git via `.gitkeep` files (`data/raw/usda/.gitkeep`, etc.).
3. **Manifest Tracked**: `data/manifest.json` is explicitly un-ignored (`!data/manifest.json`) so dataset provenance is maintained in version control.
4. **Immutability**: Raw files remain read-only once downloaded. All cleansing or subsetting produces separate outputs in `data/processed/` or streams directly into PostgreSQL.

---

## 9. Dataset-Specific Importers & Roadmap Status

1. **Step 03.2 (USDA Importer)**: **Completed (Authoritative PASS)**.
   - Package: `ingestion/datasets/usda/` (`parser.py`, `validator.py`, `loader.py`, `importer.py`).
   - Supports streaming directly from ZIP archives or extracted directories.
   - Enforces referential integrity, positive gram weights, and null preservation.
   - Detailed guide: [`docs/USDA_INGESTION.md`](USDA_INGESTION.md).
2. **Step 03.3 (Food.com Importer)**: **Completed (Authoritative PASS)**.
   - Package: `ingestion/datasets/foodcom/` (`parser.py`, `validator.py`, `ratings.py`, `loader.py`, `importer.py`).
   - Safely parses stringified Python lists via `ast.literal_eval`, prohibiting `eval()`.
   - Preserves 7-element raw %DV nutrition array verbatim in `recipe_catalog.recipe_nutrition_raw`.
   - Aggregates ~1.1M interaction reviews using temporary session staging table `temp_foodcom_ratings_staging` with $O(\text{batch\_size})$ Python memory overhead.
   - Synchronizes child records (`recipe_ingredients`, `recipe_instructions`, `recipe_tags`) with idempotent batch upserts.
   - Computes weighted full-text search vector `tsv_search` (title: A, description: B, tags: C).
   - Detailed guide: [`docs/FOODCOM_INGESTION.md`](FOODCOM_INGESTION.md).
3. **Step 03.4 (RecipeNLG Importer)**: **Completed (Authoritative PASS)**.
   - Package: `ingestion/datasets/recipenlg/` (`parser.py`, `validator.py`, `loader.py`, `importer.py`).
   - Streams `full_dataset.csv` (~2.23M recipes, ~1.8 GB) with bounded memory ($O(1)$ process overhead).
   - Dual-engine list parser: fast JSON first, fallback `ast.literal_eval`. Strictly prohibits `eval()`.
   - Additive database migration `database/migrations/005_add_recipenlg_source_origin.sql` tracks sub-corpus origin (`Gathered` vs `Recipes1M`).
   - Conservative quantity and unit extraction for raw ingredient strings.
   - Ambiguity-free canonical ingredient linking using pre-extracted NER entities.
   - Computes weighted full-text search vector `tsv_search` (title: A, ingredients: B).
   - Detailed guide: [`docs/RECIPENLG_INGESTION.md`](RECIPENLG_INGESTION.md).
4. **Step 03.5 (Stratified Sampling Engine)**: **Completed (Authoritative PASS)**.
   - Package: `ingestion/sampling/` (`base.py`, `foodcom_sampler.py`, `recipenlg_sampler.py`, `reports.py`).
   - Two-pass memory-bounded streaming architecture ($O(M)$ memory where $M$ is sample size, $O(1)$ stream buffering).
   - Food.com: Stratified across 7 primary categories (Breakfast, Lunch, Dinner, Dessert, Snack, Beverage, Other) and 5 cooking time buckets.
   - Food.com Interaction Filtering: Preserves 100% referential integrity with zero ghost interactions by retaining all reviews matching sampled recipe IDs.
   - RecipeNLG: Stratified across source origin (`Gathered` vs `Recipes1M`), 4 NER richness tiers, and directions availability.
   - Preserves complete original CSV columns verbatim without fabricating missing fields.
   - Detailed guide: [`docs/SAMPLING_GUIDE.md`](SAMPLING_GUIDE.md).

---

## 10. Development Dataset Sampling Commands

Generate representative 25,000-recipe development subsets using the CLI:

```bash
# Food.com: Stratified sample + referential interaction filtering
python -m ingestion.cli sample \
  --dataset foodcom \
  --source data/raw/foodcom \
  --output-dir data/processed/dev_sample/foodcom \
  --limit 25000 \
  --seed 42

# RecipeNLG: Stratified sample
python -m ingestion.cli sample \
  --dataset recipenlg \
  --source data/raw/recipenlg/full_dataset.csv \
  --output-dir data/processed/dev_sample/recipenlg \
  --limit 25000 \
  --seed 42
```


