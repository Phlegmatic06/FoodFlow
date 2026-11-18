# NutriPod — RecipeNLG Dataset Integration Guide

| Metadata | Details |
| :--- | :--- |
| **Pipeline Step** | Step 03.4 (RecipeNLG Large Scale Recipe Corpus Integration) |
| **Target Schema** | `recipe_catalog` (Member 2 / Port 8002) |
| **Target Tables** | `recipes`, `recipe_ingredients`, `recipe_instructions`, `canonical_ingredients`, `ingredient_synonyms`, `ingestion_provenance` |
| **Primary Dataset** | RecipeNLG (`full_dataset.csv`, 2,231,142 records, ~1.8 GB CSV) |
| **CLI Command** | `python -m ingestion.cli ingest-recipenlg --source <path>` |
| **Database Identity** | `foodflow_admin` (Administrative Ingestion / Migration Role) |
| **Required Migration** | `database/migrations/005_add_recipenlg_source_origin.sql` |

---

## 1. Dataset Origin & Scholarly Context

NutriPod utilizes the **RecipeNLG** corpus to expand its culinary catalogue to over 2 million diverse recipes with pre-extracted named entity recognition (NER) ingredient tokens.

### 1.1 Citation & Attribution
The dataset was created and published by Michał Bień, Michał Gilski, Martyna Maciejewska, Wojciech Taisner, Dawid Wisniewski, and Agnieszka Ławrynowicz at Poznań University of Technology:

> **Bień, M., Gilski, M., Maciejewska, M., Taisner, W., Wisniewski, D., & Ławrynowicz, A. (2020).**  
> *RecipeNLG: A Large Scale Dataset for Recipe Generation and Evaluation.*  
> Proceedings of the 13th International Conference on Natural Language Generation (INLG 2020), pp. 350–359. Association for Computational Linguistics.

- **Official Dataset Portal**: [https://recipenlg.cs.put.poznan.pl/dataset](https://recipenlg.cs.put.poznan.pl/dataset)

> [!WARNING]
> **Usage Agreement & Licensing Restrictions**: The official RecipeNLG website requires acceptance of a **non-commercial research and educational usage agreement**. Research associates and students working with the dataset must respect these terms. It is not an unrestricted open-content licence; do not claim CC BY-NC-SA or CC0 without verified authorization. Raw dataset files are stored in `data/raw/recipenlg/` and strictly excluded from Git and container images.

---

## 2. Source Files & Schema Specifications

The RecipeNLG archive typically unpacks into a single large CSV file.
- **Canonical filename**: `full_dataset.csv` (~2.2 GB uncompressed, 2,231,142 records).
- **Official archive member**: In the officially downloaded `archive.zip`, the CSV member is named `RecipeNLG_dataset.csv` (2,294,981,083 bytes uncompressed, 2,231,142 rows).
- **Dynamic alias resolution**: `RecipeNLGSource` automatically resolves `RecipeNLG_dataset.csv` when querying `full_dataset.csv` without requiring manual extraction or renaming.

### 2.1 Documented CSV Fields & Header Aliases
| CSV Field | Case Variations & Aliases | Type | Description |
| :--- | :--- | :--- | :--- |
| `id` | `id`, `ID`, `""` (empty string at column 0), `Unnamed: 0` | Integer | Sequential integer index starting at `0` up to `2231141`. |
| `title` | `title`, `Title`, `name` | String | Recipe title string. |
| `ingredients` | `ingredients`, `Ingredients` | Stringified List | List of raw ingredient strings (e.g., `["2 cups flour", "1 tsp salt"]`). |
| `directions` | `directions`, `Directions`, `steps` | Stringified List | List of step-by-step cooking directions. |
| `link` | `link`, `Link`, `url` | String | Original web source URL. |
| `source` | `source`, `Source` | String | Sub-corpus classification: `Gathered` or `Recipes1M`. |
| `ner` | `ner`, `NER` | Stringified List | Pre-extracted named entity recognition ingredient names (e.g., `["flour", "salt"]`). |

### 2.2 Pandas Index Header Normalization & Validation Rules
Because the source dataset was exported using pandas with `index=True`, the first column header in the raw CSV is an empty string `""` (or `Unnamed: 0` in some tools).
The ingestion validator enforces strict rules:
1. **First-Column ID Resolution**: An empty string `""` or `Unnamed: 0` is accepted as the recipe ID **only at column index 0**, and only when its row values strictly validate as non-negative integers ($\ge 0$).
2. **Rejection of Misplaced Empty Headers**: An empty or unnamed header at any non-first column index ($> 0$) is strictly rejected as invalid CSV formatting.
3. **Preservation of ID Zero**: Recipe ID `0` is a valid identifier (e.g., `rcp_nlg_0`) and is never shifted, offset, or dropped.
4. **Original ID Integrity**: Original IDs are preserved as stringified integers without modification. IDs are never substituted with row numbers or synthetic counters.

---

## 3. Physical Database Architecture & Mapping

All tables are deployed strictly within the `recipe_catalog` schema, adhering to the PostgreSQL 16 DDL defined in `database/002_create_tables.sql` and the additive migration `database/migrations/005_add_recipenlg_source_origin.sql`.

### 3.1 Entity-Relationship Overview

```
                                  +───────────────────────────+
                                  | recipe_catalog.           |
                                  | canonical_ingredients     |
                                  | • id (PK - INTEGER)       |
                                  | • name, category          |
                                  +───────────────────────────+
                                                ▲
                                                │ 0..1 (RESTRICT)
                                                │
                                  +───────────────────────────+
                                  | recipe_catalog.recipes    |
                                  | • id (PK - rcp_nlg_*)     |
                                  | • title (VARCHAR 512)     |
                                  | • source_dataset='recipenlg'
                                  | • source_origin           |
                                  | • source_url (link)       |
                                  | • tsv_search (tsvector)   |
                                  +───────────────────────────+
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        │ 1:N (CASCADE)                                 │ 1:N (CASCADE)
                        ▼                                               ▼
+─────────────────────────────────────────────+ +─────────────────────────────────────────────+
| recipe_catalog.recipe_ingredients           | | recipe_catalog.recipe_instructions          |
| • recipe_id (FK -> recipes.id)              | | • recipe_id (FK -> recipes.id)              |
| • position (SMALLINT)                       | | • step_number (SMALLINT)                    |
| • raw_text (Original string)                | | • instruction (Original text)               |
| • canonical_ingredient_id (Matched ID)      | +─────────────────────────────────────────────+
| • quantity, unit (Conservative parse)       |
+─────────────────────────────────────────────+
```

### 3.2 Field-by-Field Relational Mapping

#### 1. `recipe_catalog.recipes`
| Source CSV | Target Column | Type | Ingestion & Normalization Rule |
| :--- | :--- | :--- | :--- |
| `id` | `id` | `VARCHAR(64) PRIMARY KEY` | Prefixed unified ID: `rcp_nlg_{source_id}` (e.g., `rcp_nlg_0`, `rcp_nlg_108294`). |
| `'recipenlg'` | `source_dataset` | `VARCHAR(32) NOT NULL` | Static literal identifier `recipenlg`. |
| `id` | `source_id` | `VARCHAR(64) NOT NULL` | Exact string representation of source integer ID. |
| `title` | `title` | `VARCHAR(512) NOT NULL` | Cleaned and truncated to 512 characters. Missing/empty title is rejected. |
| `source` | `source_origin` | `VARCHAR(32) NULL` | Normalized to `'Gathered'` or `'Recipes1M'`. Added by Migration 005. |
| `link` | `source_url` | `TEXT NULL` | Original source website URL. |
| *None* | `description` | `TEXT NULL` | Stored as `NULL` (RecipeNLG does not supply recipe descriptions). |
| *None* | `prep_time_minutes` | `INTEGER NULL` | Stored as `NULL` (RecipeNLG does not record prep times). |
| *None* | `cook_time_minutes` | `INTEGER NULL` | Stored as `NULL` (RecipeNLG does not record cook times). |
| *None* | `total_time_minutes` | `INTEGER NULL` | Stored as `NULL`. |
| *None* | `servings` | `INTEGER NULL` | Stored as `NULL` (no serving yields; no artificial default). |
| *None* | `cuisine` | `VARCHAR(64) NULL` | Stored as `NULL` (unsupervised cuisine inference is prohibited). |
| *None* | `submitted_date` | `DATE NULL` | Stored as `NULL`. |
| Composite | `tsv_search` | `TSVECTOR` | Computed full-text search vector: `setweight(to_tsvector('english', title), 'A') \|\| setweight(to_tsvector('english', ingredients), 'B')`. |

#### 2. `recipe_catalog.recipe_ingredients`
| Source CSV | Target Column | Type | Ingestion & Normalization Rule |
| :--- | :--- | :--- | :--- |
| `id` | `recipe_id` | `VARCHAR(64)` | Foreign key referencing `recipes.id` (ON DELETE CASCADE). |
| Array index | `position` | `SMALLINT NOT NULL` | 1-based index preserving original recipe ingredient sequence. |
| `ingredients` | `raw_text` | `TEXT NOT NULL` | Original, unparsed ingredient string (e.g., `"2 cups all-purpose flour"`). |
| NER / Lookup | `canonical_ingredient_id` | `INTEGER NULL` | Matched against `canonical_ingredients` and `ingredient_synonyms`. `NULL` if unmatched or ambiguous. |
| Parser | `quantity` | `NUMERIC(10,3) NULL`| Parsed leading numeric amount (e.g. `2.0`, `1.5`, `0.25`). `NULL` if unquantified. |
| Parser | `unit` | `VARCHAR(32) NULL` | Normalized standard unit (e.g. `'cup'`, `'tbsp'`, `'tsp'`, `'oz'`, `'lb'`). `NULL` if unparseable. |

#### 3. `recipe_catalog.recipe_instructions`
| Source CSV | Target Column | Type | Ingestion & Normalization Rule |
| :--- | :--- | :--- | :--- |
| `id` | `recipe_id` | `VARCHAR(64)` | Foreign key referencing `recipes.id` (ON DELETE CASCADE). |
| Array index | `step_number` | `SMALLINT NOT NULL` | 1-based sequential step number. |
| `directions` | `instruction` | `TEXT NOT NULL` | Cleaned instruction step text. |

> [!NOTE]
> **Zero Fabrication Policy**: RecipeNLG does not publish ratings, nutrition information, or categorical tags. NutriPod **never** fabricates fake ratings, synthetic nutrient values, or diet tags (`recipe_ratings`, `recipe_nutrition_raw`, and `recipe_tags` have **zero** rows inserted for RecipeNLG recipes). Nutritional estimates remain uncalculated until a future USDA ingredient-matching engine can compute them transparently.

---

## 4. Additive Migration 005 (`source_origin`)

RecipeNLG includes a `source` field identifying whether a recipe was sourced from the `Gathered` web crawl or the `Recipes1M` dataset.

> [!IMPORTANT]
> **Source Provenance Derivation**: The `source_origin` field is derived strictly and exclusively from the original `source` column. The importer and sampling engine support verified encodings (`'Gathered'` / `'1'` mapped to `'Gathered'`, and `'Recipes1M'` / `'recipe1m'` / `'0'` mapped to `'Recipes1M'`). Unrecognized, non-standard, or missing values evaluate to `NULL` (or `'Unknown'` in sampling strata). Under no circumstances are recipe IDs used to infer or substitute provenance origin.

Because `source_origin` is distinct from `source_dataset` (`'recipenlg'`), `source_url`, `cuisine`, or `recipe_tags`, NutriPod provides an additive migration:

```sql
-- database/migrations/005_add_recipenlg_source_origin.sql
ALTER TABLE recipe_catalog.recipes
ADD COLUMN IF NOT EXISTS source_origin VARCHAR(32);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_recipes_source_origin'
    ) THEN
        ALTER TABLE recipe_catalog.recipes
        ADD CONSTRAINT chk_recipes_source_origin
        CHECK (source_origin IS NULL OR source_origin IN ('Gathered', 'Recipes1M'));
    END IF;
END $$;
```

> [!IMPORTANT]
> The migration is **additive and safe** for existing databases: `source_origin` is nullable, preserving all existing Food.com records as `NULL`. Migration 005 must be executed by `foodflow_admin` before running live RecipeNLG ingestion.

---

## 5. Parsing & Ingredient Normalization Design

### 5.1 Dual-Engine Safe List Parsing
RecipeNLG CSV fields (`ingredients`, `directions`, `ner`) contain serialized lists.
- **Engine 1 (Fast JSON)**: Tries `json.loads(s)` first, accommodating standard JSON double-quoted syntax.
- **Engine 2 (ast.literal_eval)**: If JSON fails (e.g. single-quoted Python literals `['item1', 'item2']`), safely parses with `ast.literal_eval`.
- **Absolute Security**: Under no circumstances is `eval()` used.
- **String Enforcement**: Every list element must evaluate strictly to a non-empty string.

### 5.2 Tolerant NER Failure Handling
If the `ner` field is malformed or unparseable, but the `ingredients` and `directions` are valid:
- The importer **does not** reject the recipe.
- It records an `ner_failures` count, flags the record, and proceeds with raw ingredient text without entity-assisted matching.

### 5.3 Ambiguity-Free Canonical Matching
To prevent erroneous pantry matching:
1. **Direct Match**: Checks if the entire raw ingredient string matches a canonical ingredient or synonym.
2. **NER-Assisted Match**: If unmatched, checks if any NER entity extracted for the recipe appears in the ingredient string and exists in the canonical dictionary.
3. **Ambiguity Rejection**: If multiple conflicting canonical IDs match the same raw ingredient line (e.g. a line mentioning both *"melted butter and white sugar"*), the canonical link is left as `NULL` and logged as an ambiguous match.

---

## 6. High-Performance Streaming & Batch Insertion

With over 2.23 million rows, memory management and transactional throughput are critical:

1. **Streaming Input**: `RecipeNLGSource` streams records lazily using binary chunking or `csv.DictReader` with high field limits (`csv.field_size_limit(2147483647)`).
2. **Batch Upserts**: Inserts recipes in configurable batch sizes (default: 1,000) using parameterized SQL.
3. **Idempotent Child Synchronization**: For each batch, child records in `recipe_ingredients` and `recipe_instructions` are cleared specifically for `recipe_id = ANY(%s)` before re-inserting, preventing duplicate key violations on re-runs while never affecting unrelated Food.com records.
4. **Transaction Safety**: Batches execute in sub-transactions. If an individual batch encounters a database error, the transaction rolls back cleanly without corrupting the catalogue.

---

## 7. Command-Line Interface (CLI) Operator Guide

The NutriPod CLI provides comprehensive administrative tooling for RecipeNLG dataset ingestion.

### 7.1 Inspect Raw Files
```powershell
python -m ingestion.cli inspect --dataset recipenlg
python -m ingestion.cli inspect --dataset recipenlg --count-rows
```

### 7.2 Verify SHA-256 Checksums
```powershell
python -m ingestion.cli verify --dataset recipenlg
```

### 7.3 Dry-Run Simulation Mode
Validate and parse RecipeNLG records without modifying PostgreSQL or manifest state:
```powershell
# Dry-run over the entire dataset
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/full_dataset.csv --dry-run

# Dry-run on a sample of 1,000 recipes for fast validation
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/full_dataset.csv --limit 1000 --dry-run
```

### 7.4 Live Ingestion
```powershell
# Set database connection string (foodflow_admin role)
$env:DATABASE_URL = "postgresql://foodflow_admin:CHANGE_ME@localhost:5432/foodflow_db"

# Apply migration 005 first
psql $env:DATABASE_URL -f database/migrations/005_add_recipenlg_source_origin.sql

# Ingest full dataset in batches of 1,000
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/full_dataset.csv --batch-size 1000

# Ingest from official ZIP archive directly without extracting to disk
python -m ingestion.cli ingest-recipenlg --source data/raw/recipenlg/recipenlg.zip --batch-size 1000
```

---

## 8. Manifest Tracking & Audit Reporting

### 8.1 State Transitions
The dataset entry in `data/manifest.json` tracks lifecycle progression:
- `not_downloaded`: Default state before local file placement.
- `downloaded`: File discovered on disk.
- `verified`: SHA-256 checksum matches expected manifest value.
- `completed`: Ingestion successfully completed into `recipe_catalog`.

### 8.2 Audit Reports
Every run generates a timestamped quality audit JSON report at `data/reports/recipenlg_ingestion_<YYYYMMDD_HHMMSS>.json`, recording:
- `total_source_rows`
- `accepted_recipes`
- `rejected_rows` (with CSV line numbers and error reasons)
- `duplicate_source_ids`
- `empty_titles`
- `missing_or_malformed_ingredients`
- `missing_directions_recipes`
- `ner_failures`
- `canonical_links`
- `ambiguous_ingredient_matches`

