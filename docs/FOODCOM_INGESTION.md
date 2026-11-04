# FoodFlow — Food.com Recipes & Interactions Dataset Integration Guide

| Metadata | Details |
| :--- | :--- |
| **Pipeline Step** | Step 03.3 (Food.com Recipes & Interactions Ingestion) |
| **Target Schema** | `recipe_catalog` (Member 2 / Port 8002) |
| **Target Tables** | `recipes`, `recipe_ingredients`, `recipe_instructions`, `recipe_tags`, `recipe_nutrition_raw`, `recipe_ratings`, `canonical_ingredients`, `ingestion_provenance` |
| **Primary Datasets** | Food.com Recipes (`RAW_recipes.csv`) & User Interactions (`RAW_interactions.csv`) |
| **CLI Command** | `python -m ingestion.cli ingest-foodcom --source <path> [--component all\|recipes\|interactions]` |
| **Database Identity** | `foodflow_admin` (Administrative Ingestion / Migration Role) |

---

## 1. Dataset Origin & Scholarly Context

FoodFlow utilizes the historical **Food.com Recipes and User Interactions** dataset to populate its recipe catalog, historical review metrics, and instruction search indices.

### 1.1 Citation & Provenance
The dataset was assembled and published by Bodhisattwa Prasad Majumder, Shuyang Li, Jianmo Ni, and Julian McAuley for research in personalized recipe generation:

> **Majumder, B. P., Li, S., Ni, J., & McAuley, J. (2019).**  
> *Generating Personalized Recipes from Historical User Preferences.*  
> Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP), pp. 5976–5982, Hong Kong, China. Association for Computational Linguistics.

- **Official Research Platform Record**: [https://berd-platform.de/records/0455w-b0633](https://berd-platform.de/records/0455w-b0633)
- **Kaggle Distribution**: [https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions](https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions)

> [!WARNING]
> **Licensing & Legal Status**: The BERD platform record does **not** attach an open redistribution license such as CC0 or CC-BY. Ingestion into FoodFlow is conducted strictly for non-commercial academic research and educational evaluation. Commercial deployment or redistribution of raw or derivative recipe text is strictly prohibited. Raw datasets are stored in `data/raw/foodcom/` and excluded from git version control.

---

## 2. Source Files & Archive Structure

The importer supports reading directly from either an uncompressed directory or a zipped archive (`.zip`) without prior extraction to disk.

### 2.1 File Inventory
| File Name | Mandatory | Record Count | Target Database Table | Description |
| :--- | :---: | :---: | :--- | :--- |
| `RAW_recipes.csv` | **Yes** | 231,637 | `recipe_catalog.recipes`<br>`recipe_catalog.recipe_ingredients`<br>`recipe_catalog.recipe_instructions`<br>`recipe_catalog.recipe_tags`<br>`recipe_catalog.recipe_nutrition_raw` | Full recipe metadata, steps, ingredients, tags, and %DV nutrition arrays. |
| `RAW_interactions.csv` | **Yes** | 1,132,367 | `recipe_catalog.recipe_ratings` | User review star ratings (1–5) and feedback timestamps. |

---

## 3. Physical Database Architecture & Mapping

All tables are deployed strictly within the `recipe_catalog` schema, adhering to the PostgreSQL 16 DDL defined in `database/002_create_tables.sql` and indexes defined in `database/003_indexes.sql`.

### 3.1 Entity-Relationship Overview

```
                                  +───────────────────────────+
                                  | recipe_catalog.           |
                                  | canonical_ingredients     |
                                  | • id (PK - UUID)          |
                                  | • name, category          |
                                  +───────────────────────────+
                                                ▲
                                                │ 0..1 (RESTRICT)
                                                │
                                  +───────────────────────────+
                                  | recipe_catalog.recipes    |
                                  | • id (PK - rcp_foodcom_*) |
                                  | • title, description      |
                                  | • total_time_minutes      |
                                  | • source_dataset          |
                                  | • tsv_search (tsvector)   |
                                  +───────────────────────────+
                                                │
         ┌───────────────────┬──────────────────┼──────────────────┬──────────────────┐
         │ 1:N (CASCADE)     │ 1:N (CASCADE)    │ 1:N (CASCADE)    │ 1:1 (CASCADE)    │ 1:1 (CASCADE)
         ▼                   ▼                  ▼                  ▼                  ▼
+─────────────────+ +─────────────────+ +─────────────────+ +─────────────────+ +─────────────────+
| recipe_catalog. | | recipe_catalog. | | recipe_catalog. | | recipe_catalog. | | recipe_catalog. |
| recipe_         | | recipe_         | | recipe_         | | recipe_         | | recipe_         |
| ingredients     | | instructions    | | tags            | | nutrition_raw   | | ratings         |
| • recipe_id     | | • recipe_id     | | • recipe_id     | | • recipe_id(PK) | | • recipe_id(PK) |
| • position      | | • step_number   | | • tag (VARCHAR) | | • raw_calories  | | • rating_average|
| • raw_text      | | • instruction   | +─────────────────+ | • raw_*_pdv     | | • rating_count  |
| • canonical_id  | +─────────────────+                     +─────────────────+ +─────────────────+
+─────────────────+
```

### 3.2 Field-by-Field Relational Mapping

#### 1. `recipe_catalog.recipes`
| Source CSV (`RAW_recipes.csv`) | Target Column | Type | Transformation / Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `id` | `id` | `VARCHAR(64) PRIMARY KEY` | Prefixed with `rcp_foodcom_{id}` (e.g. `rcp_foodcom_137739`). |
| `'food_com'` | `source_dataset` | `VARCHAR(32) NOT NULL` | Static literal identifier `food_com`. |
| `name` | `title` | `VARCHAR(512) NOT NULL` | Trimmed and strictly truncated to 512 characters. |
| `description` | `description` | `TEXT NULL` | Null if empty or whitespace-only. |
| `minutes` | `total_time_minutes` | `INTEGER NULL` | Parsed positive integer. If > 43,200 min (sentinel value), stored as NULL. |
| `NULL` | `prep_time_minutes` | `INTEGER NULL` | Stored as NULL (Food.com does not publish separate prep time). |
| `NULL` | `cook_time_minutes` | `INTEGER NULL` | Stored as NULL (Food.com does not publish separate cook time). |
| `NULL` | `servings` | `INTEGER NULL` | Stored as NULL (Food.com RAW_recipes does not provide serving yields). |
| `NULL` | `cuisine` | `VARCHAR(64) NULL` | Stored as NULL (unsupervised cuisine inference is prohibited). |
| Dynamic | `source_url` | `VARCHAR(512) NULL` | Canonical Web URL: `https://www.food.com/recipe/{id}`. |
| `submitted` | `submitted_date` | `DATE NULL` | YYYY-MM-DD date string. |
| Composite | `tsv_search` | `TSVECTOR` | Computed full-text search vector: `setweight(to_tsvector('english', title), 'A') \|\| setweight(to_tsvector('english', description), 'B') \|\| setweight(to_tsvector('english', tags), 'C')`. |

#### 2. `recipe_catalog.recipe_ingredients`
| Source CSV (`RAW_recipes.csv`) | Target Column | Type | Transformation / Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `id` | `recipe_id` | `VARCHAR(64)` | Foreign key referencing `recipes.id` (ON DELETE CASCADE). |
| Array index | `position` | `INTEGER NOT NULL` | 1-based index preserving original recipe ingredient sequence. |
| `ingredients` | `raw_text` | `TEXT NOT NULL` | Raw ingredient name string extracted from Python list. |
| Taxonomy lookup | `canonical_ingredient_id` | `UUID NULL` | Matched against `canonical_ingredients.name` or synonym index. |
| `NULL` | `quantity` | `NUMERIC(10,3) NULL`| NULL (Food.com RAW_recipes provides tokenized ingredient names). |
| `NULL` | `unit` | `VARCHAR(32) NULL` | NULL. |

#### 3. `recipe_catalog.recipe_instructions`
| Source CSV (`RAW_recipes.csv`) | Target Column | Type | Transformation / Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `id` | `recipe_id` | `VARCHAR(64)` | Foreign key referencing `recipes.id` (ON DELETE CASCADE). |
| Array index | `step_number` | `INTEGER NOT NULL` | 1-based step counter preserving instructional ordering. |
| `steps` | `instruction` | `TEXT NOT NULL` | Cleaned instruction step text. |

#### 4. `recipe_catalog.recipe_tags`
| Source CSV (`RAW_recipes.csv`) | Target Column | Type | Transformation / Ingestion Rule |
| :--- | :--- | :--- | :--- |
| `id` | `recipe_id` | `VARCHAR(64)` | Foreign key referencing `recipes.id` (ON DELETE CASCADE). |
| `tags` | `tag` | `VARCHAR(128) NOT NULL`| Lowercased, stripped, truncated to 128 chars, deduplicated per recipe. |

#### 5. `recipe_catalog.recipe_nutrition_raw`
Food.com stores nutritional info as a 7-element array: `[calories, total_fat, sugar, sodium, protein, saturated_fat, carbohydrates]`.
> [!IMPORTANT]
> Food.com stores values as **% Daily Value (%DV)** based on a standard 2,000 kcal diet (except calories in kcal). FoodFlow stores these values **verbatim** in `recipe_nutrition_raw` without fabricated gram-weight conversions.

| Source Array Index | Target Column | Type | Unit / Semantic Meaning |
| :---: | :--- | :--- | :--- |
| `[0]` | `raw_calories` | `NUMERIC(10, 2)` | Energy (kcal) |
| `[1]` | `raw_total_fat_pdv` | `NUMERIC(6, 2)` | Total Fat (% Daily Value) |
| `[2]` | `raw_sugar_pdv` | `NUMERIC(6, 2)` | Sugars (% Daily Value) |
| `[3]` | `raw_sodium_pdv` | `NUMERIC(6, 2)` | Sodium (% Daily Value) |
| `[4]` | `raw_protein_pdv` | `NUMERIC(6, 2)` | Protein (% Daily Value) |
| `[5]` | `raw_saturated_fat_pdv` | `NUMERIC(6, 2)` | Saturated Fat (% Daily Value) |
| `[6]` | `raw_carbohydrates_pdv` | `NUMERIC(6, 2)` | Carbohydrates (% Daily Value) |

#### 6. `recipe_catalog.recipe_ratings`
| Calculation Source | Target Column | Type | Semantic Meaning |
| :--- | :--- | :--- | :--- |
| `recipe_id` | `recipe_id` | `VARCHAR(64) PRIMARY KEY` | Foreign key referencing `recipes.id` (ON DELETE CASCADE). |
| Incremental Average | `rating_average` | `NUMERIC(3, 2) NULL` | Mathematical mean `ROUND(rating_sum / rating_count, 2)`. NULL if 0 ratings. |
| Incremental Count | `rating_count` | `INTEGER NOT NULL` | Total count of validated user reviews. Defaults to 0. |
| Timestamp | `updated_at` | `TIMESTAMPTZ NOT NULL` | Timestamp when ratings were last computed. |

---

## 4. Key Architectural Safeguards

### 4.1 Safe Evaluation of Stringified Python Lists
Food.com CSV columns (`ingredients`, `steps`, `tags`, `nutrition`) contain Python-style string representations of lists.
- **NEVER use Python's built-in `eval()`**: It presents a severe code-injection vulnerability.
- **Strict `ast.literal_eval` implementation**: The parser inspects opening and closing square brackets `[` and `]`, rejecting syntax with malformed boundaries before delegating to `ast.literal_eval`.
- **Syntax validation**: Only Python literals (lists, strings, numbers) are allowed. Function calls, comprehensions, and variable lookups raise `FoodComParseError`.

### 4.2 Sentinel Cooking Times
Food.com contains numerous records with sentinel cooking times (e.g. `2147483647` minutes, `1000000` minutes).
- Values exceeding **43,200 minutes** (30 days) are recognized as unrecorded durations.
- Rather than rejecting otherwise valid recipes, the importer stores `total_time_minutes` as `NULL` and logs a warning for auditing.

### 4.3 Scalable Ratings Aggregation Architecture
`RAW_interactions.csv` contains **1,132,367 interaction records**. Holding dictionaries of this size in Python process memory causes memory bloat and risks out-of-memory errors on modest developer workstations.

```
                    RAW_interactions.csv (1.13M rows)
                                    │
                                    ▼ (Streaming in batches of 5,000)
                     validate_interaction_record()
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ PostgreSQL Temporary Session Staging Table             │
       │ temp_foodcom_ratings_staging                           │
       │ (recipe_id VARCHAR(64) PK, rating_sum, rating_count)   │
       └────────────────────────────────────────────────────────┘
                                    │
               ON CONFLICT (recipe_id) DO UPDATE SET            │ (Incremental sum & count)
               rating_sum = staging.rating_sum + EXCLUDED.sum   │
                                    │
                                    ▼
       ┌────────────────────────────────────────────────────────┐
       │ Commit to Permanent Table: recipe_ratings              │
       │ SELECT s.recipe_id,                                    │
       │   ROUND((s.rating_sum / s.rating_count)::numeric, 2),  │
       │   s.rating_count                                       │
       │ FROM temp_foodcom_ratings_staging s                    │
       │ JOIN recipes r ON r.id = s.recipe_id                   │
       │ WHERE r.source_dataset = 'food_com'                    │
       └────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                   DROP TABLE temp_foodcom_ratings_staging
```

1. **Streaming Input**: Interactions are read line-by-line via `open_csv_stream`.
2. **Session Temporary Table**: Creates an unlogged session table `temp_foodcom_ratings_staging`.
3. **Exact Incremental Upsert**: Python batches sums and counts for 5,000 rows at a time, sending a single `executemany` upsert query to accumulate sums and counts in PostgreSQL.
4. **Zero Rounding Drift**: Computing average only at final transfer guarantees exact mathematical averages `ROUND(rating_sum / rating_count, 2)`.
5. **Safe Clean-up**: The staging table is dropped in a `finally` block, ensuring no temporary table remains if an error occurs.

---

## 5. Command-Line Interface (CLI) Operator Guide

The FoodFlow CLI provides comprehensive administrative tooling for Food.com dataset ingestion.

### 5.1 Inspect Raw Files
Inspect local raw CSV presence, column headers, and optional line counts:
```powershell
python -m ingestion.cli inspect --dataset foodcom
python -m ingestion.cli inspect --dataset foodcom --count-rows
```

### 5.2 Verify SHA-256 Checksums
Verify that local files match the expected manifest checksums:
```powershell
python -m ingestion.cli verify --dataset foodcom
```

### 5.3 Dry-Run Simulation Mode
Validate and parse the dataset without modifying PostgreSQL tables or updating the manifest:
```powershell
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --dry-run
```

### 5.4 Live Ingestion
Perform full live ingestion using the administrative database connection:
```powershell
# Set database connection string
$env:DATABASE_URL = "postgresql://foodflow_admin:CHANGE_ME@localhost:5432/foodflow_db"

# Ingest both recipes and interaction ratings (default: --component all)
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/

# Ingest recipes only (sets manifest to partially_imported)
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --component recipes

# Ingest ratings only (requires recipes to be ingested first)
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --component interactions
```

### 5.5 Development & Testing Limits
Limit row processing for fast development iterations:
```powershell
python -m ingestion.cli ingest-foodcom --source data/raw/foodcom/ --limit-recipes 1000 --limit-interactions 5000 --batch-size 500 --dry-run
```

---

## 6. Manifest Tracking & Audit Reporting

### 6.1 State Transitions
The dataset lifecycle in `data/manifest.json` transitions systematically:
- `not_downloaded`: Default state on initial setup.
- `downloaded`: Files discovered locally.
- `verified`: SHA-256 checksums match expected values.
- `partially_imported`: `RAW_recipes.csv` ingested successfully into `recipe_catalog`.
- `completed`: Both recipes and historical interaction ratings ingested.

### 6.2 Quality Audit Reports
Every dry-run or live ingestion writes a timestamped JSON audit log to `data/reports/foodcom_ingestion_<YYYYMMDD_HHMMSS>.json`. This report details:
- Exact row counts read, accepted, and rejected.
- Sample rejected lines with line numbers and human-readable error reasons.
- Unique tag counts, instruction counts, and ratings metrics.
- Source path, execution mode, and duration.

