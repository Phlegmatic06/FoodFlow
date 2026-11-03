# FoodFlow — Dataset Plan & Ingestion Strategy

| Metadata | Details |
| :--- | :--- |
| **Document Version** | 1.0.0 |
| **Status** | Approved Dataset Specification (Pre-Implementation) |
| **Datasets Analyzed** | USDA FoodData Central, RecipeNLG, Food.com Recipes & Interactions |
| **Storage & Database** | PostgreSQL 16 (`recipe_catalog` & `profile_nutrition` schemas) |

---

## 1. Dataset Matrix & Provenance Overview

FoodFlow integrates three distinct datasets to power recipe exploration, nutrition verification, and pantry matching:

```
+───────────────────────────+ +───────────────────────────+ +───────────────────────────+
|     DATASET 1: USDA FDC   | |    DATASET 2: RECIPENLG   | |   DATASET 3: FOOD.COM     |
| (Ingredient Composition)  | |  (Large Recipe Corpus)    | | (Metadata & Interactions) |
+───────────────────────────+ +───────────────────────────+ +───────────────────────────+
| • Download: fdc.nal.usda  | | • recipenlg.cs.put.poznan | | • berd-platform.de/records|
| • ~8,000 SR/Foundation   | | • ~2.23 Million Recipes   | | • ~231k Recipes           |
| • Nutrient composition   | | • Titles, NER Ingredients | | • Interactions dataset    |
| • Macro/micronutrients    | | • Step directions         | | • Historical ratings (1-5)|
| • Public Domain / CC0 1.0 | | • Research/Edu Agreement  | | • Rights require verif.   |
+───────────────────────────+ +───────────────────────────+ +───────────────────────────+
              │                             │                             │
              ▼                             ▼                             ▼
+───────────────────────────────────────────────────────────────────────────────────────+
|                      REPRODUCIBLE DATA INGESTION UTILITY PIPELINE                     |
|                   (Standalone Python Batch CLI Scripts & Cleaners)                    |
+───────────────────────────────────────────────────────────────────────────────────────+
                                            │
                                            ▼
+───────────────────────────────────────────────────────────────────────────────────────+
|                                    POSTGRESQL 16                                      |
|            (Canonical IDs, Provenance Preserved, GIN Text Indices, Zero Bloat)        |
+───────────────────────────────────────────────────────────────────────────────────────+
```

---

## 2. Dataset Deep Dives

### 2.1 Dataset 1: USDA FoodData Central (FDC)
- **Official Source**: [https://fdc.nal.usda.gov/download-datasets/](https://fdc.nal.usda.gov/download-datasets/)
- **Target Subsets**: 
  - **SR Legacy (Standard Reference)**: Authoritative historic composition data for staple ingredients (vegetables, meats, grains, spices).
  - **Foundation Foods**: Modern nutrient analyses containing detailed per-100g values for basic commodity ingredients.
- **Key Tables / Files**:
  - `food.csv`: `fdc_id`, `data_type`, `description`, `publication_date`.
  - `nutrient.csv`: `id`, `name`, `unit_name`, `nutrient_nbr`.
  - `food_nutrient.csv`: `id`, `fdc_id`, `nutrient_id`, `amount` (standardized per 100g).
  - `food_portion.csv`: `fdc_id`, `seq_num`, `amount`, `measure_unit_id`, `gram_weight`.
- **Contribution to FoodFlow**: Serves as the reference nutritional dictionary. Powers the **Profile and Nutrition Service** (Member 1) to match raw recipe ingredients with macro- and micronutrients per 100g.
- **Licensing & Legal**: U.S. Government public work; dedicated to the public domain under **CC0 1.0 Universal**. Recommended academic attribution to the USDA Agricultural Research Service.
- **Ingestion Pipeline Specification**: See [`docs/USDA_INGESTION.md`](USDA_INGESTION.md) for the complete streaming architecture, schema mappings, CLI commands, and integrity rules.

### 2.2 Dataset 2: RecipeNLG
- **Official Source**: [https://recipenlg.cs.put.poznan.pl/dataset](https://recipenlg.cs.put.poznan.pl/dataset)
- **Primary Reference**: Bień, M., Gilski, M., Maciejewska, M., Taisner, W., Wisniewski, D., & Lawrynowicz, A. (2020). *RecipeNLG: A Large Scale Dataset for Recipe Generation and Evaluation*.
- **Volume**: ~2,231,142 recipe records in raw distribution.
- **Format**: CSV (`full_dataset.csv`, ~1.8 GB uncompressed).
- **Core Columns**:
  - `id`: Sequential integer index.
  - `title`: Recipe title string.
  - `ingredients`: Stringified JSON array of raw ingredient text (e.g., `["2 cups flour", "1 tsp baking powder"]`).
  - `directions`: Stringified JSON array of cooking instructions.
  - `link`: Original web source URL.
  - `source`: Web domain category (e.g., `Gathered`, `Allrecipes`).
  - `NER`: Pre-extracted named entity recognition list of ingredient names (e.g., `["flour", "baking powder"]`).
- **Contribution to FoodFlow**: Provides a vast, diverse corpus of recipe instructions and titles for the Recipe and Ingredient Service (Member 2). The `NER` column drastically accelerates ingredient tokenization and canonical taxonomy normalization, consumed via REST by the Recommendation and Meal Planner Service (Member 3) for pantry matching.
- **Licensing & Legal Terms**: The official RecipeNLG website requires acceptance of a **non-commercial research and educational usage agreement**. It must not be labeled under a Creative Commons license (such as CC BY-NC-SA 4.0) unless independently verified with the authors.
  - **Compliance Directive**: FoodFlow is strictly an academic, non-commercial university coursework project. All usage maintains explicit academic attribution and citations to Bień et al. (2020). Raw dataset files are never committed to version control or redistributed.
- **Ingestion Pipeline Specification**: See [`docs/RECIPENLG_INGESTION.md`](RECIPENLG_INGESTION.md) for the streaming parser, conservative quantity parsing, NER canonical linking, and additive migration `005_add_recipenlg_source_origin.sql`.

### 2.3 Dataset 3: Food.com Recipes and Interactions
- **Dataset Registry**: [https://berd-platform.de/records/0455w-b0633](https://berd-platform.de/records/0455w-b0633)
- **Primary Reference**: Majumder, B. P., Li, S., Ni, J., & McAuley, J. (2019). *Generating Personalized Recipes from Historical User Preferences*. EMNLP.
- **Files & Structure**:
  - `RAW_recipes.csv` (~231,637 recipes):
    - `name`: Recipe title.
    - `id`: Food.com recipe unique identifier.
    - `minutes`: Preparation and cooking time in minutes.
    - `contributor_id`: Food.com author identifier.
    - `submitted`: Date of submission.
    - `tags`: Formatted array of tags (e.g., `['30-minutes-or-less', 'vegetarian', 'dinner']`).
    - `nutrition`: 7-element float array: `[calories (kcal), total_fat (%DV), sugar (%DV), sodium (%DV), protein (%DV), saturated_fat (%DV), carbohydrates (%DV)]`.
    - `n_steps`: Number of instruction steps.
    - `steps`: Stringified list of step-by-step instructions.
    - `description`: Author editorial overview.
    - `ingredients`: Stringified list of ingredient names.
    - `n_ingredients`: Count of ingredients.
  - `RAW_interactions.csv`:
    - `user_id`, `recipe_id`, `date`, `rating` (1–5 scale), `review` (text).
    - *Row Count Note*: Research literature commonly cites ~1.1M interaction records. The actual row count varies across specific release archives; FoodFlow calculates and logs the exact row count directly from the downloaded file version upon ingestion rather than hardcoding an unverified figure.
- **Contribution to FoodFlow**: Delivers rich metadata (prep times, difficulty tags, cuisine categories), community quality signals (ratings and reviews), and source-reported %DV nutritional profiles for Member 2 (`recipe_catalog`), consumed via REST by Member 3 (Meal Planner Service) for plan scheduling and Member 1 (Profile & Nutrition Service) for nutrition caching.
- **Licensing & Legal Terms**: The BERD repository record does not assign a standardized open license. Rights and access conditions require verification before any public distribution. In FoodFlow, this data is used strictly within the bounds of university educational research and evaluation. Original contributor attribution and source IDs are strictly preserved.
- **Ingestion Pipeline Specification**: See [`docs/FOODCOM_INGESTION.md`](FOODCOM_INGESTION.md) for the complete streaming architecture, schema mappings, CLI commands, %DV nutrition array semantics, and incremental ratings aggregation architecture.

---

## 3. Data Provenance & Unique Identifier Strategy

To prevent ID collisions across distinct sources, FoodFlow enforces a **synthetic unified primary key** alongside explicit source provenance attributes:

```
+───────────────────────────────────────────────────────────────────────────────────────+
|                                UNIFIED RECIPE IDENTIFIER                              |
|                    Format: rcp_{source_dataset}_{source_id}                           |
|                                                                                       |
| Examples:                                                                             |
| • Food.com:   rcp_foodcom_5421     (source_dataset: 'food_com',  source_id: '5421')   |
| • RecipeNLG:  rcp_nlg_108294       (source_dataset: 'recipenlg', source_id: '108294') |
+───────────────────────────────────────────────────────────────────────────────────────+
```

### 3.1 Provenance Tracking Schema
Every ingestion run records metadata in a dedicated provenance log table (`recipe_catalog.ingestion_provenance`):
- `source_dataset` (e.g., `'usda_fdc'`, `'food_com'`, `'recipenlg'`)
- `source_url`
- `download_timestamp`
- `dataset_version`
- `file_sha256_checksum`
- `original_raw_row_count`
- `imported_row_count`
- `skipped_malformed_count`
|                    Format: rcp_{source_dataset}_{source_id}                           |
|                                                                                       |
| Examples:                                                                             |
| • Food.com:   rcp_foodcom_5421     (source_dataset: 'food_com',  source_id: '5421')   |
| • RecipeNLG:  rcp_nlg_108294       (source_dataset: 'recipenlg', source_id: '108294') |
+───────────────────────────────────────────────────────────────────────────────────────+
```

### Table Schema for Recipe Provenance (`recipe_catalog.recipes`)
```sql
CREATE TABLE recipe_catalog.recipes (
    id VARCHAR(64) PRIMARY KEY,                  -- e.g. 'rcp_foodcom_5421'
    source_dataset VARCHAR(32) NOT NULL,         -- 'food_com' | 'recipenlg'
    source_id VARCHAR(64) NOT NULL,             -- Original upstream ID
    title VARCHAR(512) NOT NULL,
    description TEXT,
    prep_time_minutes INTEGER CHECK (prep_time_minutes >= 0),
    cook_time_minutes INTEGER CHECK (cook_time_minutes >= 0),
    total_time_minutes INTEGER CHECK (total_time_minutes >= 0),
    servings INTEGER CHECK (servings > 0),       -- Strictly NULL when unrecorded; NO artificial default of 4
    cuisine VARCHAR(64),
    source_url TEXT,
    submitted_date DATE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    tsv_search TSVECTOR,                         -- Full-text search vector
    CONSTRAINT uq_recipes_source UNIQUE (source_dataset, source_id)
);

CREATE UNIQUE INDEX idx_recipes_source ON recipe_catalog.recipes (source_dataset, source_id);
CREATE INDEX idx_recipes_tsv_search ON recipe_catalog.recipes USING GIN (tsv_search);
CREATE INDEX idx_recipes_title_trgm ON recipe_catalog.recipes USING GIN (title gin_trgm_ops);
```

---

## 4. Preprocessing & Data Cleaning Requirements

### 4.1 RecipeNLG Preprocessing
1. **Stringified List Parsing**: The raw CSV contains strings representing Python lists (e.g., `'["1 cup sugar", "2 eggs"]'`). The cleaner safely parses these using JSON decoders or Python `ast.literal_eval`.
2. **Text Normalization**: Strips escaped quotes (`\"`), irregular whitespace, and non-printable characters.
3. **Ingredient Structure Extraction**: Uses the provided `NER` column to isolate the canonical ingredient name, while preserving the raw ingredient string for display.
4. **Instruction Splitting**: Converts raw strings into structured instruction steps numbered sequentially ($1, 2, 3 \dots$).

### 4.2 Food.com Preprocessing
1. **Preservation of Raw Percentage Daily Values (PDV)**:
   Food.com stores nutrition as a 7-element array:
   $$\text{nutrition} = [\text{calories (kcal)}, \text{total\_fat (\%DV)}, \text{sugar (\%DV)}, \text{sodium (\%DV)}, \text{protein (\%DV)}, \text{sat\_fat (\%DV)}, \text{carbs (\%DV)}]$$
   - *Data Integrity Directive*: FoodFlow stores these raw PDV values directly in `recipe_catalog.recipe_nutrition` (`raw_calories`, `raw_total_fat_pdv`, `raw_sugar_pdv`, `raw_sodium_pdv`, `raw_protein_pdv`, `raw_saturated_fat_pdv`, `raw_carbohydrates_pdv`). **PDV percentages must never be presented as directly measured grams.**
   - *Approximation for Gram Display*: When the user interface displays estimated grams for macros, they are calculated based on standard reference daily intake values (FDA 2,000 kcal reference diet: Total Fat 78g, Saturated Fat 20g, Carbohydrates 275g, Protein 50g, Sodium 2,300mg):
     $$\text{approx\_fat\_g} = \frac{\%DV \times 78}{100}, \quad \text{approx\_carbs\_g} = \frac{\%DV \times 275}{100}, \quad \text{approx\_protein\_g} = \frac{\%DV \times 50}{100}$$
   - *Labeling Rule*: All resulting gram values are labeled as *"Approximate Gram Equivalents based on FDA 2,000 kcal Daily Values"* and are explicitly distinguished from chemical laboratory assays or verified measurements.
2. **Tag Cleansing**: Filters out generic noise tags (e.g., `'time-to-make'`, `'course'`) while retaining high-value taxonomy tags (e.g., `'vegetarian'`, `'mexican'`, `'under-30-minutes'`).
3. **Ratings Aggregation**: Aggregates `RAW_interactions.csv` to compute `rating_average = AVG(rating)` and `rating_count = COUNT(rating)` per `recipe_id` for ratings $> 0$.

### 4.3 Deduplication Strategy
- **Exact Matches**: Recipes with normalized title matches and identical ingredient sets are linked via a `canonical_recipe_id` pointer rather than blindly purged, preserving user interaction history from Food.com.
- **Cross-Source Redundancy**: If a recipe appears in both RecipeNLG and Food.com, the Food.com record takes precedence for display due to its prep times, ratings, and nutritional metadata.

---

## 5. Nutrition Matching & Confidence Strategy

```
+───────────────────────────────────────────────────────────────────────────────────────+
|                           NUTRITIONAL RESOLUTION PIPELINE                             |
+───────────────────────────────────────────────────────────────────────────────────────+
                                            │
         ┌──────────────────────────────────┴──────────────────────────────────┐
         ▼                                                                     ▼
+─────────────────────────────────+                   +─────────────────────────────────+
|   SOURCE HAS PRE-COMPUTED DATA  |                   |   SOURCE LACKS NUTRITION DATA   |
|         (e.g., Food.com)        |                   |        (e.g., RecipeNLG)        |
+─────────────────────────────────+                   +─────────────────────────────────+
                 │                                                     │
                 ▼                                                     ▼
+─────────────────────────────────+                   +─────────────────────────────────+
| Store raw PDV values            |                   | Check quantity & unit parsing:  |
| Calculate approximate grams     |                   | Are quantities reliably parsed? |
| Label: "Source-Reported PDV"    |                   +─────────────────────────────────+
| Status: 'reported_approximate'  |                                    │
+─────────────────────────────────+                         ┌──────────┴──────────┐
                                                            ▼                     ▼
                                                   [Reliable Quantities]  [Missing Quantities]
                                                            │                     │
                                                            ▼                     ▼
                                                   Match against USDA    Status: 'uncalculated'
                                                   FoodData Central      (Return nulls)
                                                            │                     │
                                                            ▼                     ▼
                                                   Coverage Check        Display: "Nutrition
                                                   (Provisional ≥80%     Unavailable"
                                                   heuristic rule)       STRICTLY ZERO
                                                            │            FABRICATED VALUES
                                                   ┌────────┴────────┐
                                                   ▼                 ▼
                                            [≥ 80% Validated]  [< 80% Mapped]
                                                   │                 │
                                                   ▼                 ▼
                                            Status:            Status:
                                            'calculated'       'uncalculated'
```

### 5.1 The Zero-Fabrication & Scientific Integrity Policy
1. **Never Guess or Fabricate Macronutrients**: Under no circumstances will FoodFlow fabricate missing calories or macronutrients.
2. **RecipeNLG Nutrition Constraints**: RecipeNLG provides ingredient text strings and NER tokens, but lacks structured numeric gram weights and units. **Nutrition can only be calculated when ingredient quantities, units, and USDA food mappings are sufficiently reliable.** If reliable quantities cannot be parsed, the system does not attempt caloric calculation, returning `status: 'uncalculated'` with `null` fields.
3. **Provisional 80% Mapping Heuristic**: The proposed requirement that at least 80% of ingredients be mapped to USDA entries is a **provisional project heuristic rule**, not an established scientific standard. It will be evaluated and tuned during Phase 2 development.
4. **No "USDA-Verified" Mislabeling**: Derived nutritional values must never be labeled as "USDA-verified". They are strictly labeled as *"Calculated Estimate based on USDA ingredient mapping"*, while Food.com values are labeled as *"Source-Reported % Daily Values"*.

---

## 6. Reproducible Ingestion Pipeline Execution

### 6.1 Storage & Git Hygiene
- **Strict Rule**: Raw CSV/JSON files (ranging from hundreds of megabytes to gigabytes) **must never be committed to Git** or embedded inside application container images.
- All raw datasets reside in a git-ignored host directory: `data/raw/`.
- Preprocessed seeds reside in `data/processed/`.

### 6.2 Ingestion Architecture & Utility Tooling
The ingestion engine consists of standalone Python CLI utility scripts (`ingestion/` directory), **not a fourth runtime microservice**:

```bash
# Step 1: Download & verify checksums (executed on host or staging environment)
python -m ingestion.cli download --dataset usda
python -m ingestion.cli download --dataset foodcom
python -m ingestion.cli download --dataset recipenlg

# Step 2: Seed USDA nutrient dictionary into profile_nutrition schema
python -m ingestion.cli ingest-usda --source data/raw/usda/

# Step 3: Seed development subset (benchmark target: 25,000 recipes per dataset for local testing)
python -m ingestion.cli ingest-recipes --source data/raw/foodcom/ --limit 25000
python -m ingestion.cli ingest-recipes --source data/raw/recipenlg/ --limit 25000

# Step 4: Ingest historical ratings & interactions
python -m ingestion.cli ingest-ratings --source data/raw/foodcom/RAW_interactions.csv
```

### 6.3 Development Sampling vs Full Production Scale & Broad Coverage
- **Broad General-Purpose Coverage**: FoodFlow is architected as a comprehensive, general-purpose culinary and cooking platform, not exclusively a health recipe filter. Search and discovery must support everyday weeknight dinners, comfort foods, regional cuisines (Asian, Latin, Mediterranean, European, etc.), baking, desserts, snacks, and beverages.
- **Stratified Development Sampling**:
  - The local development target (25,000 Food.com + 25,000 RecipeNLG recipes + full USDA SR-Legacy dictionary) is a **temporary seed**.
  - The sampling strategy in `ingestion/` must use **stratified sampling across categories, tags, cuisines, and ingredient lengths**, rather than taking the first 25,000 sequential rows of raw CSVs.
  - Total dev DB footprint: $< 1.2 \text{ GB}$ (measured goal for laptop comfort).
- **Full Production Catalogue Scale**:
  - The ingestion pipeline supports both `--limit` sampling and full dataset ingestion (`--full`).
  - Target production scale: full usable collections (~231k Food.com recipes and ~2.23M RecipeNLG records), staged and benchmarked on dedicated storage.
  - Ingestion runtimes and search latencies are benchmark targets to be measured and validated during testing, not guaranteed upfront.
- **Search Ranking & Empty State Policy**:
  - Discovery combines PostgreSQL `tsvector` FTS with `pg_trgm` similarity. **Exact title matches are scored and prioritized ahead of fuzzy or related results.**
  - Zero recipe fabrication: if no exact match is found, the application displays an honest empty state with related suggestions from the actual catalogue, never synthetic or fabricated dishes.
  - Missing preparation times, servings, and nutrition are represented transparently as unknown.

