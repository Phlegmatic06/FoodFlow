# NutriPod — USDA FoodData Central Dataset Integration Guide

| Metadata | Details |
| :--- | :--- |
| **Pipeline Step** | Step 03.2 (USDA FoodData Central Ingestion) |
| **Target Schema** | `profile_nutrition` (Member 1 / Port 8001) |
| **Target Tables** | `usda_foods`, `usda_nutrients`, `usda_food_nutrients`, `usda_food_portions`, `ingestion_provenance` |
| **Supported Collections** | Foundation Foods (October 2026 release) & SR Legacy (April 2018 final release) |
| **CLI Command** | `python -m ingestion.cli ingest-usda --data-type [foundation|sr-legacy] --source <path>` |
| **Database Identity** | `foodflow_admin` (Administrative Ingestion / Migration Role) |

---

## 1. Official USDA Data Sources & Scope

NutriPod uses **USDA FoodData Central (FDC)** as the authoritative nutritional composition dictionary to calculate energy (kcal) and macronutrient breakdowns (fat, carbs, protein, fiber, sodium) per 100g for recipe ingredients.

### 1.1 Selected Collections
NutriPod specifically ingests two curated USDA collections and deliberately excludes the multi-gigabyte commercial Branded Foods dataset:

1. **Foundation Foods (October 2026 Release)**:
   - **Download URL**: [https://fdc.nal.usda.gov/download-datasets/](https://fdc.nal.usda.gov/download-datasets/)
   - **Characteristics**: Modern nutrient analyses containing detailed per-100g values for basic agricultural commodity ingredients (e.g., fresh produce, whole grains, meats, dairy).
   - **Typical Volume**: ~8,000 foods with granular lab derivations and household portions.
   - **Data Type Tag**: `foundation_food`

2. **SR Legacy (Standard Reference Legacy — April 2018 Final Release)**:
   - **Download URL**: [https://fdc.nal.usda.gov/download-datasets/](https://fdc.nal.usda.gov/download-datasets/)
   - **Characteristics**: Historic baseline composition data for staple ingredients and prepared commodity items.
   - **Typical Volume**: ~7,793 foods with extensive multi-nutrient coverage.
   - **Data Type Tag**: `sr_legacy_food`

> [!IMPORTANT]
> **Licensing & Legal Terms**: USDA FoodData Central is a work of the United States Government and is in the public domain under **CC0 1.0 Universal**. Attribution is maintained to the *U.S. Department of Agriculture, Agricultural Research Service*. Raw dataset archives are downloaded manually and never committed to version control.

---

## 2. Archive Structure & Source Handling

The importer supports two storage formats:
1. **Official Downloaded ZIP Archives**: Reads CSV members directly through Python's `zipfile` module in binary streaming mode. **No full archive extraction to disk is required.**
2. **Extracted Directory Trees**: Recursively discovers CSV files in root or nested subdirectories (e.g. `FoodData_Central_foundation_foods_csv_2026-10/`).

### Expected CSV Files
| File Name | Mandatory | Target Database Table | Description |
| :--- | :---: | :--- | :--- |
| `food.csv` | **Yes** | `profile_nutrition.usda_foods` | Core food catalog and classification |
| `nutrient.csv` | **Yes** | `profile_nutrition.usda_nutrients` | Nutrient definition dictionary (Energy, Protein, etc.) |
| `food_nutrient.csv` | **Yes** | `profile_nutrition.usda_food_nutrients` | Measured nutrient amounts per 100g edible portion |
| `food_portion.csv` | Optional | `profile_nutrition.usda_food_portions` | Household serving weights (e.g. "1 cup" = 120g) |

*Note*: Supporting files such as `measure_unit.csv`, `food_category.csv`, or `derivation_code_description.csv` may be present in the official download archive. The importer inspects archive members, extracts the core required files, and ignores non-essential metadata tables without error.

---

## 3. Physical Database Mapping

All tables reside strictly within the `profile_nutrition` schema, adhering to the PostgreSQL 16 DDL defined in `database/002_create_tables.sql`:

```
                                  +───────────────────────────+
                                  | profile_nutrition.        |
                                  | usda_foods                |
                                  | • fdc_id (PK)             |
                                  | • data_type               |
                                  | • description             |
                                  | • publication_date        |
                                  +───────────────────────────+
                                                │
                       ┌────────────────────────┴────────────────────────┐
                       │ 1:N (CASCADE)                                   │ 1:N (CASCADE)
                       ▼                                                 ▼
+───────────────────────────+ +───────────────────────────+   +───────────────────────────+
| profile_nutrition.        | | profile_nutrition.        |   | profile_nutrition.        |
| usda_nutrients            | | usda_food_nutrients       |   | usda_food_portions        |
| • id (PK)                 | | • id (PK)                 |   | • id (PK)                 |
| • name                    | | • fdc_id (FK -> foods)    |   | • fdc_id (FK -> foods)    |
| • unit_name               | | • nutrient_id (FK -> nuts)|   | • amount, seq_num         |
| • nutrient_nbr            | | • amount (per 100g)       |   | • portion_description     |
+───────────────────────────+ +───────────────────────────+   | • gram_weight (NOT NULL)  |
                       ▲               │                      +───────────────────────────+
                       └───────────────┘
                         1:N (RESTRICT)
```

### 3.1 Field-by-Field Mapping Matrix

#### `profile_nutrition.usda_foods`
| Source CSV (`food.csv`) | Target Column | Type | Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `fdc_id` | `fdc_id` | `INTEGER PRIMARY KEY` | Mandatory positive integer. |
| `data_type` | `data_type` | `VARCHAR(32) NOT NULL` | Value from CSV or defaults to collection tag (`foundation_food`, `sr_legacy_food`). |
| `description` | `description` | `TEXT NOT NULL` | Cleaned and trimmed food description. |
| `food_category_id` | `food_category_id` | `INTEGER NULL` | USDA category grouping identifier. |
| `publication_date` | `publication_date` | `DATE NULL` | YYYY-MM-DD date string. |

#### `profile_nutrition.usda_nutrients`
| Source CSV (`nutrient.csv`) | Target Column | Type | Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `id` | `id` | `INTEGER PRIMARY KEY` | USDA nutrient identifier (e.g. 1003 for Protein). |
| `name` | `name` | `VARCHAR(128) NOT NULL` | Display name of the nutrient. |
| `unit_name` | `unit_name` | `VARCHAR(16) NOT NULL` | Measurement unit (`G`, `MG`, `UG`, `KCAL`). Preserved verbatim. |
| `nutrient_nbr` | `nutrient_nbr` | `VARCHAR(16) NULL` | Standard USDA nutrient reference number. |
| `rank` | `rank` | `NUMERIC(8,2) NULL` | Display and sorting priority. |

#### `profile_nutrition.usda_food_nutrients`
| Source CSV (`food_nutrient.csv`) | Target Column | Type | Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `id` | `id` | `INTEGER PRIMARY KEY` | Authoritative measurement row identifier. |
| `fdc_id` | `fdc_id` | `INTEGER NOT NULL FK` | Verified against `usda_foods`. Cascades on food deletion. |
| `nutrient_id` | `nutrient_id` | `INTEGER NOT NULL FK` | Verified against `usda_nutrients`. Restricted on deletion. |
| `amount` | `amount` | `NUMERIC(12,4) NULL` | Quantity per 100g edible portion. **NULL if empty; never defaulted to 0.** |
| `data_points` | `data_points` | `INTEGER NULL` | Number of laboratory analyses combined. |
| `derivation_id` | `derivation_id` | `INTEGER NULL` | USDA analytical derivation code. |

#### `profile_nutrition.usda_food_portions`
| Source CSV (`food_portion.csv`) | Target Column | Type | Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `id` | `id` | `INTEGER PRIMARY KEY` | Authoritative portion row identifier. |
| `fdc_id` | `fdc_id` | `INTEGER NOT NULL FK` | Target food identifier. |
| `seq_num` | `seq_num` | `INTEGER NULL` | Display sequence number. |
| `amount` | `amount` | `NUMERIC(8,3) NULL` | Quantity of measure units (e.g., 1.0). |
| `measure_unit_id` | `measure_unit_id` | `INTEGER NULL` | Unit identifier. |
| `portion_description` | `portion_description` | `VARCHAR(255) NULL` | Text description (e.g., "1 cup", "1 slice"). |
| `modifier` | `modifier` | `VARCHAR(128) NULL` | Preparation modifier (e.g., "chopped", "cooked"). |
| `gram_weight` | `gram_weight` | `NUMERIC(10,3) NOT NULL` | Mandatory positive gram weight equivalent. |

---

## 4. Data Quality & Integrity Rules

1. **Zero Fabrication**:
   - If a nutrient amount is unmeasured or blank in USDA files, it is stored as `NULL`. It is **never** replaced with `0.0`.
   - The importer does not guess or invent serving portions if `food_portion.csv` omits a food item.
2. **Exact Unit Preservation**:
   - Nutrient measurement units (`G`, `MG`, `UG`, `KCAL`, `KJ`) are imported exactly as specified in USDA master data. No arbitrary runtime unit conversions are performed during ingestion.
3. **Referential Integrity Enforcement**:
   - `food_nutrient.csv` records referencing unknown `fdc_id`s or unknown `nutrient_id`s are rejected with line-numbered audit logs.
4. **Shared Nutrient Consistency**:
   - Both Foundation Foods and SR Legacy contain `nutrient.csv`. Nutrient definitions are inserted using `ON CONFLICT (id) DO NOTHING`. If an incoming record conflicts with an existing nutrient name or unit, a warning is logged, and the existing authoritative record is preserved.
5. **Idempotent Re-runs**:
   - Tables are **never truncated or dropped**.
   - Foods, food nutrients, and portions use `ON CONFLICT (id/fdc_id) DO UPDATE` to safely refresh metadata and amounts without creating duplicates.

---

## 5. Dependency-Ordered Execution Order

To satisfy foreign key constraints in PostgreSQL, ingestion strictly follows this execution sequence:

```
Step 1: usda_foods (food.csv)
        └─> Loads foods into profile_nutrition.usda_foods; collects valid fdc_ids in memory.

Step 2: usda_nutrients (nutrient.csv)
        └─> Loads master nutrient dictionary; collects valid nutrient_ids in memory.

Step 3: usda_food_nutrients (food_nutrient.csv)
        └─> Streams and validates against known food and nutrient IDs; loads measurements.

Step 4: usda_food_portions (food_portion.csv, if present)
        └─> Streams and validates against known food IDs; loads portion conversions.

Step 5: profile_nutrition.ingestion_provenance
        └─> Commits audit log containing file name, SHA-256 hash, and record counts.

Step 6: data/manifest.json
        └─> Updates collection status, imported row counts, and last ingestion timestamp.
```

---

## 6. CLI Usage & Operations

### 6.1 Inspecting Local USDA Files
```powershell
python -m ingestion.cli inspect --dataset usda
```

### 6.2 Dry-Run Validation (No Database Writes)
Validates CSV headers, parses fields, tests foreign key constraints, and counts rows without modifying PostgreSQL:
```powershell
# Foundation Foods dry-run from directory
python -m ingestion.cli ingest-usda --data-type foundation --source data/raw/usda/foundation --dry-run

# SR Legacy dry-run from ZIP archive with limit
python -m ingestion.cli ingest-usda --data-type sr-legacy --source data/raw/usda/sr_legacy.zip --dry-run --limit 500
```

### 6.3 Live Ingestion
Executes batch insertions into PostgreSQL under the `foodflow_admin` role:
```powershell
# Set database connection URL
$env:DATABASE_URL="postgresql://foodflow_admin:CHANGE_ME@localhost:5432/foodflow_db"

# 1. Ingest Foundation Foods
python -m ingestion.cli ingest-usda --data-type foundation --source data/raw/usda/foundation --batch-size 1000

# 2. Ingest SR Legacy
python -m ingestion.cli ingest-usda --data-type sr-legacy --source data/raw/usda/sr_legacy.zip --batch-size 1000
```

### 6.4 Status Dashboard
```powershell
python -m ingestion.cli status
```

---

## 7. Troubleshooting & Error Recovery

| Error / Symptom | Root Cause | Resolution |
| :--- | :--- | :--- |
| `DatabaseConfigurationError: DATABASE_URL is not set` | Attempting live ingestion without connection URL. | Set `$env:DATABASE_URL` or run with `--dry-run`. |
| `DependencyMissingError: psycopg is not installed` | Missing PostgreSQL database driver. | Run `pip install -r ingestion/requirements.txt`. |
| `USDAParseError: missing required files` | Source archive missing `food.csv` or `nutrient.csv`. | Verify archive was not corrupted during manual download. |
| `Foreign key violation: fdc_id ... not found` | `food_nutrient.csv` contains an orphan food record. | Importer automatically rejects orphan record and logs sample. |
| `Missing mandatory gram_weight` | Portion record has blank gram equivalent. | Importer rejects the individual portion record to protect NOT NULL constraint. |
| `Permission denied for schema profile_nutrition` | Connected as wrong database role. | Ingestion must connect as `foodflow_admin` (or `postgres`). Service roles cannot cross schemas. |

