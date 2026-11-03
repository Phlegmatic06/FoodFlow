# FoodFlow — Database Schema & Data Architecture Reference

| Metadata | Details |
| :--- | :--- |
| **Document Version** | 1.0.0 |
| **Status** | Implementation-Ready Engineering Reference (Step 02 Baseline) |
| **Target Engine** | PostgreSQL 16 (with `pgcrypto` and `pg_trgm` extensions) |
| **Database Name** | `foodflow_db` |
| **Logical Partitioning** | 3 Service-Isolated Schemas (`profile_nutrition`, `recipe_catalog`, `meal_planner`) |
| **Authoritative Source DDL** | `database/001_create_schemas.sql`, `002_create_tables.sql`, `003_indexes.sql`, `004_permissions.sql` |

---

## 1. PostgreSQL 16 Architecture & Schema Isolation

FoodFlow deploys a **single PostgreSQL 16 instance** partitioned into **three strictly isolated schemas**. This topology eliminates the resource overhead of operating three separate database containers on student hardware while enforcing microservice boundary rules:

```
                                  +------------------------------------+
                                  |         POSTGRESQL 16 ENGINE       |
                                  |         (foodflow_db : 5432)       |
                                  +------------------------------------+
                                                    │
         ┌──────────────────────────────────────────┼──────────────────────────────────────────┐
         ▼                                          ▼                                          ▼
+────────────────────────────────+ +────────────────────────────────+ +────────────────────────────────+
|   SCHEMA: profile_nutrition    | |    SCHEMA: recipe_catalog      | |     SCHEMA: meal_planner       |
|   (Owned by Member 1, :8001)   | |    (Owned by Member 2, :8002)  | |     (Owned by Member 3, :8003) |
+────────────────────────────────+ +────────────────────────────────+ +────────────────────────────────+
| • usda_foods                   | | • canonical_ingredients        | | • guest_sessions               |
| • usda_nutrients               | | • ingredient_synonyms          | | • pantry_sessions              |
| • usda_food_nutrients          | | • recipes                      | | • pantry_session_items         |
| • usda_food_portions           | | • recipe_ingredients           | | • meal_plans                   |
| • nutrition_estimates          | | • recipe_instructions          | | • meal_plan_slots              |
| • ingestion_provenance         | | • recipe_tags                  | | • shopping_lists               |
|                                | | • recipe_ratings               | | • shopping_list_items          |
|                                | | • recipe_nutrition_raw         | |                                |
|                                | | • ingestion_provenance         | |                                |
+────────────────────────────────+ +────────────────────────────────+ +────────────────────────────────+
```

### 1.1 Strict Boundary Rules & Isolation Rationale
1. **Zero Cross-Schema Foreign Keys**:
   - `meal_planner.meal_plan_slots.recipe_id` stores a plain string (`VARCHAR(64)`), referencing `recipe_catalog.recipes.id` strictly by convention, without a database constraint.
   - `meal_planner.pantry_session_items.canonical_ingredient_id` stores an integer identifier, referencing `recipe_catalog.canonical_ingredients.id` without a foreign key.
   - `profile_nutrition.nutrition_estimates.recipe_id` stores a plain string (`VARCHAR(64)`), referencing `recipe_catalog.recipes.id` without a foreign key.
2. **Zero Cross-Schema Joins**:
   - Application microservices connect using least-privilege roles that have permission to read/write **only** their own schema.
   - SQL queries joining across schemas (e.g. `SELECT * FROM meal_planner.meal_plan_slots s JOIN recipe_catalog.recipes r ON s.recipe_id = r.id`) are **forbidden and technically blocked** by PostgreSQL permissions.
   - All cross-domain data aggregation is conducted via synchronous inter-service REST calls.
3. **Why External References Lack Foreign Keys**:
   - **Independent Evolution**: If Member 2 drops, truncates, or reindexes `recipe_catalog.recipes` during dataset updates or migrations, Member 3's `meal_planner` schema remains unaffected and unblocked.
   - **Service Decoupling**: Enforcing foreign keys across schemas would require database-level coordination between services, preventing independent deployment, independent backup/restore, and future database sharding.
   - **Resilience to Missing Records**: A guest may have a meal plan slot containing an ID that has been deprecated or unindexed upstream; the planner displays the cached `recipe_title` snapshot rather than crashing on foreign key integrity failures.

---

## 2. Comprehensive Schema & Table Reference

### 2.1 Schema 1: `profile_nutrition` (Member 1 / Port 8001)
*Role Owner*: `foodflow_profile_user`  
*Domain*: USDA FoodData Central nutritional library, nutrient portions, and recipe estimation cache.

#### Table: `profile_nutrition.usda_foods`
Stores food commodity and reference items imported from USDA FoodData Central (`food.csv`).
- `fdc_id` (`INTEGER PRIMARY KEY`): Authoritative USDA integer identifier.
- `data_type` (`VARCHAR(32) NOT NULL`): USDA source subset (`sr_legacy_food`, `foundation_food`, `survey_fndds_food`).
- `description` (`TEXT NOT NULL`): Descriptive food name (e.g., "Oats, whole grain, rolled").
- `food_category_id` (`INTEGER NULL`): Optional USDA food category grouping.
- `publication_date` (`DATE NULL`): Publication date in USDA repository.
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`): Import audit timestamp.

#### Table: `profile_nutrition.usda_nutrients`
Master dictionary of nutrient types from USDA FDC (`nutrient.csv`).
- `id` (`INTEGER PRIMARY KEY`): Authoritative USDA nutrient identifier (e.g., 1003 for Protein).
- `name` (`VARCHAR(128) NOT NULL`): Nutrient display name.
- `unit_name` (`VARCHAR(16) NOT NULL`): Measurement unit (`G`, `MG`, `UG`, `KCAL`).
- `nutrient_nbr` (`VARCHAR(16) NULL`): Standard USDA nutrient number.
- `rank` (`NUMERIC(8,2) NULL`): Sorting and display priority rank.

#### Table: `profile_nutrition.usda_food_nutrients`
Measured laboratory nutrient values per 100g edible portion (`food_nutrient.csv`).
- `id` (`INTEGER PRIMARY KEY`): Authoritative record identifier from USDA.
- `fdc_id` (`INTEGER NOT NULL REFERENCES profile_nutrition.usda_foods(fdc_id) ON DELETE CASCADE`): Target food item.
- `nutrient_id` (`INTEGER NOT NULL REFERENCES profile_nutrition.usda_nutrients(id) ON DELETE RESTRICT`): Measured nutrient.
- `amount` (`NUMERIC(12,4) NULL`): Quantity per 100g edible portion. NULL if unmeasured.
- `data_points` (`INTEGER NULL`): Number of laboratory analyses combined.
- `derivation_id` (`INTEGER NULL`): USDA derivation methodology identifier.

#### Table: `profile_nutrition.usda_food_portions`
Household serving portion descriptions and gram weights (`food_portion.csv`).
- `id` (`INTEGER PRIMARY KEY`): USDA portion record identifier.
- `fdc_id` (`INTEGER NOT NULL REFERENCES profile_nutrition.usda_foods(fdc_id) ON DELETE CASCADE`): Target food item.
- `seq_num` (`INTEGER NULL`): Display sequence number.
- `amount` (`NUMERIC(8,3) NULL`): Quantity of measure units (e.g., 1.0).
- `measure_unit_id` (`INTEGER NULL`): Unit identifier.
- `portion_description` (`VARCHAR(255) NULL`): Text representation (e.g., "1 cup", "1 slice").
- `modifier` (`VARCHAR(128) NULL`): Preparation modifier (e.g., "cooked", "uncooked", "diced").
- `gram_weight` (`NUMERIC(10,3) NOT NULL`): Authoritative gram equivalent for the household measure.

#### Table: `profile_nutrition.nutrition_estimates`
Caches aggregated nutritional estimates for recipes, populated by the calculation engine or ingestion pipelines.
- `recipe_id` (`VARCHAR(64) PRIMARY KEY`): External reference (`rcp_{dataset}_{id}`). **NO cross-schema foreign key.**
- `status` (`VARCHAR(32) NOT NULL CHECK (status IN ('calculated', 'uncalculated', 'reported_approximate'))`): Provenance status.
- `calories_kcal` (`NUMERIC(10,2) NULL`): Estimated energy in kilocalories.
- `total_fat_g` (`NUMERIC(8,2) NULL`), `saturated_fat_g` (`NUMERIC(8,2) NULL`), `carbohydrates_g` (`NUMERIC(8,2) NULL`), `sugar_g` (`NUMERIC(8,2) NULL`), `protein_g` (`NUMERIC(8,2) NULL`), `sodium_mg` (`NUMERIC(8,2) NULL`), `fiber_g` (`NUMERIC(8,2) NULL`).
- `ingredient_coverage_pct` (`NUMERIC(5,2) NULL`): Percentage of recipe ingredients mapped to USDA items.
- `mapped_ingredient_count` (`INTEGER NULL`), `total_ingredient_count` (`INTEGER NULL`), `servings` (`INTEGER NULL`).
- `provenance_note` (`TEXT NULL`): Audit text detailing mapping formulas or source notes.
- `calculated_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`), `updated_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

#### Table: `profile_nutrition.ingestion_provenance`
Audit log recording raw USDA file downloads, checksums, and imported row counts.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `source_dataset` (`VARCHAR(32) NOT NULL`): e.g. `'usda_fdc'`.
- `source_url` (`TEXT NOT NULL`), `download_timestamp` (`TIMESTAMP WITH TIME ZONE NOT NULL`), `dataset_version` (`VARCHAR(64) NULL`).
- `file_name` (`VARCHAR(255) NOT NULL`), `file_sha256_checksum` (`VARCHAR(64) NOT NULL`).
- `original_raw_row_count` (`INTEGER NULL`), `imported_row_count` (`INTEGER NULL`), `skipped_malformed_count` (`INTEGER NOT NULL DEFAULT 0`).
- `ingested_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`), `ingested_by` (`VARCHAR(64) NOT NULL DEFAULT CURRENT_USER`), `notes` (`TEXT NULL`).

---

### 2.2 Schema 2: `recipe_catalog` (Member 2 / Port 8002)
*Role Owner*: `foodflow_recipe_user`  
*Domain*: Multi-source recipe catalogue, ingredients, instructions, tags, ratings, raw Food.com nutrition, and normalization taxonomy.

#### Table: `recipe_catalog.canonical_ingredients`
Normalized ingredient dictionary used for synonym mapping and pantry match scoring.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `name` (`VARCHAR(255) NOT NULL UNIQUE`): Normalized lowercase ingredient token (e.g., "chicken breast").
- `category` (`VARCHAR(64) NULL`): Supermarket department (`produce`, `dairy`, `poultry`, `meat`, `seafood`, `pantry_staple`, `spice`, `grain`, `other`).
- `is_pantry_staple` (`BOOLEAN NOT NULL DEFAULT FALSE`): Indicates common household staples (salt, pepper, water) eligible for exclusion during pantry matching.
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

#### Table: `recipe_catalog.ingredient_synonyms`
Variant spellings, raw terms, and pluralizations resolving to a canonical ingredient.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `synonym` (`VARCHAR(255) NOT NULL UNIQUE`): Raw token (e.g., "boneless skinless chicken thighs").
- `canonical_ingredient_id` (`INTEGER NOT NULL REFERENCES recipe_catalog.canonical_ingredients(id) ON DELETE CASCADE`).
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

#### Table: `recipe_catalog.recipes`
Unified core catalogue combining Food.com and RecipeNLG records.
- `id` (`VARCHAR(64) PRIMARY KEY`): Prefixed identifier (`rcp_foodcom_5421` or `rcp_nlg_108294`).
- `source_dataset` (`VARCHAR(32) NOT NULL`): Origin indicator (`food_com` or `recipenlg`).
- `source_id` (`VARCHAR(64) NOT NULL`): Raw identifier from the source CSV.
- `source_origin` (`VARCHAR(32) NULL CHECK (source_origin IS NULL OR source_origin IN ('Gathered', 'Recipes1M'))`): Sub-corpus origin for RecipeNLG recipes. Added via additive migration `database/migrations/005_add_recipenlg_source_origin.sql`. NULL for Food.com records.
- `title` (`VARCHAR(512) NOT NULL`): Recipe title.
- `description` (`TEXT NULL`): Editorial overview (Food.com) or null.
- `prep_time_minutes` (`INTEGER NULL CHECK (prep_time_minutes >= 0)`): Active prep duration.
- `cook_time_minutes` (`INTEGER NULL CHECK (cook_time_minutes >= 0)`): Active cooking duration.
- `total_time_minutes` (`INTEGER NULL CHECK (total_time_minutes >= 0)`): Total duration.
- `servings` (`INTEGER NULL CHECK (servings > 0)`): Recipe yield. **Strictly NULL when unknown; no false default of 4.**
- `cuisine` (`VARCHAR(64) NULL`): Regional or cultural cuisine classification.
- `source_url` (`TEXT NULL`), `submitted_date` (`DATE NULL`), `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).
- `tsv_search` (`TSVECTOR NULL`): Full-text search vector over title, description, and tags. Maintained by ingestion.
- `CONSTRAINT uq_recipes_source UNIQUE (source_dataset, source_id)`: Prevents duplicate upstream imports.

#### Table: `recipe_catalog.recipe_ingredients`
Ordered ingredients belonging to a recipe, preserving the original string alongside parsed tokens.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `recipe_id` (`VARCHAR(64) NOT NULL REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE`).
- `position` (`SMALLINT NOT NULL`): 1-indexed ingredient order within the recipe.
- `raw_text` (`TEXT NOT NULL`): Verbatim ingredient line from source (e.g., "2 cups all-purpose flour, sifted").
- `canonical_ingredient_id` (`INTEGER NULL REFERENCES recipe_catalog.canonical_ingredients(id) ON DELETE SET NULL`): Normalized taxonomy link.
- `quantity` (`NUMERIC(10,3) NULL`), `unit` (`VARCHAR(32) NULL`).
- `CONSTRAINT uq_recipe_ingredients_pos UNIQUE (recipe_id, position)`.

#### Table: `recipe_catalog.recipe_instructions`
Sequential preparation steps.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `recipe_id` (`VARCHAR(64) NOT NULL REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE`).
- `step_number` (`SMALLINT NOT NULL`): 1-indexed sequence order.
- `instruction` (`TEXT NOT NULL`): Verbatim instruction text.
- `CONSTRAINT uq_recipe_instructions_step UNIQUE (recipe_id, step_number)`.

#### Table: `recipe_catalog.recipe_tags`
Categorical, dietary, and occasion tags.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `recipe_id` (`VARCHAR(64) NOT NULL REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE`).
- `tag` (`VARCHAR(128) NOT NULL`): Normalized lowercase tag.
- `CONSTRAINT uq_recipe_tags_recipe_tag UNIQUE (recipe_id, tag)`.

#### Table: `recipe_catalog.recipe_ratings`
Historical review statistics aggregated from Food.com interaction records (`RAW_interactions.csv`).
- `recipe_id` (`VARCHAR(64) PRIMARY KEY REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE`).
- `rating_average` (`NUMERIC(3,2) NULL CHECK (rating_average >= 0.0 AND rating_average <= 5.0)`): Average rating (1.00 to 5.00). **Strictly NULL if unrated; never defaulted to 5.0.**
- `rating_count` (`INTEGER NOT NULL DEFAULT 0 CHECK (rating_count >= 0)`): Number of reviews.
- `updated_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

#### Table: `recipe_catalog.recipe_nutrition_raw`
Stores the original Food.com 7-element nutrition array as percentage Daily Values (%DV).
- `recipe_id` (`VARCHAR(64) PRIMARY KEY REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE`).
- `raw_calories` (`NUMERIC(10,2) NOT NULL`): Reported energy in kilocalories (kcal).
- `raw_total_fat_pdv` (`NUMERIC(8,2) NULL`), `raw_sugar_pdv` (`NUMERIC(8,2) NULL`), `raw_sodium_pdv` (`NUMERIC(8,2) NULL`), `raw_protein_pdv` (`NUMERIC(8,2) NULL`), `raw_saturated_fat_pdv` (`NUMERIC(8,2) NULL`), `raw_carbohydrates_pdv` (`NUMERIC(8,2) NULL`).
- *Integrity Rule*: All `raw_*_pdv` values represent percentage of daily value, not measured grams. No database generated columns are used for gram conversions. Approximate grams are computed in application logic and explicitly labeled.

#### Table: `recipe_catalog.ingestion_provenance`
Audit log tracking Food.com and RecipeNLG downloads, SHA-256 hashes, and imported record counts. Identical structure to `profile_nutrition.ingestion_provenance`.

---

### 2.3 Schema 3: `meal_planner` (Member 3 / Port 8003)
*Role Owner*: `foodflow_planner_user`  
*Domain*: Anonymous guest sessions, active pantry inventories, meal plans, slot execution progress, and grocery shopping lists.

#### Table: `meal_planner.guest_sessions`
Enables guest-first personalization without mandatory registration.
- `id` (`UUID PRIMARY KEY DEFAULT gen_random_uuid()`): Session token passed in HTTP header `X-Guest-Session-ID`.
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).
- `expires_at` (`TIMESTAMP WITH TIME ZONE NOT NULL`): Expiration boundary (default 30 days from creation).
- `last_active_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`): Updated on session access.

#### Table: `meal_planner.pantry_sessions`
Active pantry inventory container for a guest.
- `id` (`UUID PRIMARY KEY DEFAULT gen_random_uuid()`).
- `guest_session_id` (`UUID NULL REFERENCES meal_planner.guest_sessions(id) ON DELETE SET NULL`).
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`), `updated_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

#### Table: `meal_planner.pantry_session_items`
Individual ingredients stored in a user pantry.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `pantry_session_id` (`UUID NOT NULL REFERENCES meal_planner.pantry_sessions(id) ON DELETE CASCADE`).
- `canonical_ingredient_id` (`INTEGER NULL`): External reference to `recipe_catalog.canonical_ingredients.id`. **NO cross-schema foreign key.**
- `raw_name` (`VARCHAR(255) NOT NULL`): Free-form user ingredient name.
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).
- `CONSTRAINT uq_pantry_session_items_raw UNIQUE (pantry_session_id, raw_name)`.

#### Table: `meal_planner.meal_plans`
Multi-day meal planning container (1 to 14 days).
- `id` (`UUID PRIMARY KEY DEFAULT gen_random_uuid()`).
- `guest_session_id` (`UUID NULL REFERENCES meal_planner.guest_sessions(id) ON DELETE SET NULL`).
- `name` (`VARCHAR(255) NOT NULL DEFAULT 'My Meal Plan'`).
- `target_calories_kcal` (`INTEGER NULL CHECK (target_calories_kcal > 0)`): Optional daily caloric ceiling or goal.
- `days` (`SMALLINT NOT NULL DEFAULT 1 CHECK (days >= 1 AND days <= 14)`): Schedule length.
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`), `updated_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

#### Table: `meal_planner.meal_plan_slots`
Allocates recipes to specific days and meal slot types, incorporating cooking execution state directly.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `plan_id` (`UUID NOT NULL REFERENCES meal_planner.meal_plans(id) ON DELETE CASCADE`).
- `day_index` (`SMALLINT NOT NULL CHECK (day_index >= 0)`): 0-indexed day within the plan.
- `slot_type` (`VARCHAR(16) NOT NULL CHECK (slot_type IN ('breakfast', 'lunch', 'dinner', 'snack'))`).
- `recipe_id` (`VARCHAR(64) NOT NULL`): External reference (`rcp_{dataset}_{id}`). **NO cross-schema foreign key.**
- `recipe_title` (`VARCHAR(512) NOT NULL`): Denormalized title snapshot for offline and history display.
- `cooking_status` (`VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (cooking_status IN ('pending', 'cooked', 'skipped'))`): Cooking execution state. Eliminates redundant progress tracking tables.
- `status_updated_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`), `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).
- `CONSTRAINT uq_meal_plan_slots_entry UNIQUE (plan_id, day_index, slot_type, recipe_id)`.

#### Table: `meal_planner.shopping_lists`
Consolidated grocery checklist tied 1:1 to a meal plan.
- `id` (`UUID PRIMARY KEY DEFAULT gen_random_uuid()`).
- `plan_id` (`UUID NOT NULL REFERENCES meal_planner.meal_plans(id) ON DELETE CASCADE UNIQUE`).
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`), `updated_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

#### Table: `meal_planner.shopping_list_items`
Checklist items grouped by supermarket aisle.
- `id` (`INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY`).
- `shopping_list_id` (`UUID NOT NULL REFERENCES meal_planner.shopping_lists(id) ON DELETE CASCADE`).
- `ingredient_name` (`VARCHAR(255) NOT NULL`): Consolidate item name.
- `quantity_display` (`VARCHAR(64) NULL`): Formatted quantity string (e.g., "3 lbs", "2 heads").
- `category` (`VARCHAR(64) NULL`): Department grouping (`Produce`, `Dairy`, `Meat`, `Pantry Staples`, `Other`).
- `checked` (`BOOLEAN NOT NULL DEFAULT FALSE`): Procurement checklist state.
- `created_at` (`TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()`).

---

## 3. Index Inventory & Search Strategy

The database includes 33 purpose-built indexes in `database/003_indexes.sql`:

```
+───────────────────────────────────────────────────────────────────────────────────────────+
|                                    INDEX DISTRIBUTION MATRIX                              |
+──────────────────────────┬────────────────────────────┬───────────────────────────────────+
| SCHEMA                   | INDEX NAME                 | TARGET COLUMN & PURPOSE           |
+──────────────────────────┼────────────────────────────┼───────────────────────────────────+
| **profile_nutrition**    | idx_usda_foods_data_type   | (data_type) — B-tree filtering     |
|                          | idx_usda_foods_desc_trgm   | GIN (description gin_trgm_ops)    |
|                          | idx_usda_nutrients_fdc_id  | (fdc_id) — FK lookup              |
|                          | idx_usda_nutrients_nutr_id | (nutrient_id) — FK lookup         |
|                          | idx_usda_nutrients_comp    | (fdc_id, nutrient_id) — Composite |
|                          | idx_usda_portions_fdc_id   | (fdc_id) — FK lookup              |
|                          | idx_nutrition_estimates_st | (status) — Cache status lookup    |
+──────────────────────────┼────────────────────────────┼───────────────────────────────────+
| **recipe_catalog**       | idx_recipes_tsv_search     | GIN (tsv_search) — Full-text FTS  |
|                          | idx_recipes_title_trgm     | GIN (title gin_trgm_ops) — Fuzzy  |
|                          | idx_recipes_source_dataset | (source_dataset) — B-tree filter  |
|                          | idx_recipes_total_time_flt | (total_time_minutes) WHERE NOT NULL|
|                          | idx_recipes_cuisine_flt    | (cuisine) WHERE NOT NULL          |
|                          | idx_recipes_servings_flt   | (servings) WHERE NOT NULL         |
|                          | idx_recipe_ingred_rcp_id   | (recipe_id) — FK lookup           |
|                          | idx_recipe_ingred_canon_id | (canonical_id) WHERE NOT NULL     |
|                          | idx_recipe_instruct_rcp_id | (recipe_id) — FK lookup           |
|                          | idx_recipe_tags_rcp_id     | (recipe_id) — FK lookup           |
|                          | idx_recipe_tags_tag        | (tag) — Tag search                |
|                          | idx_recipe_ratings_ranking | (rating_avg DESC NULLS LAST, cnt) |
|                          | idx_canon_ingred_category  | (category) WHERE NOT NULL         |
|                          | idx_canon_ingred_name_trgm | GIN (name gin_trgm_ops) — Fuzzy   |
|                          | idx_ingred_syn_canon_id    | (canonical_id) — FK lookup        |
|                          | idx_ingred_syn_syn_trgm    | GIN (synonym gin_trgm_ops) — Fuzzy|
+──────────────────────────┼────────────────────────────┼───────────────────────────────────+
| **meal_planner**         | idx_guest_sess_expires_at  | (expires_at) — Session expiry     |
|                          | idx_guest_sess_last_active | (last_active_at) — Cleanup audit  |
|                          | idx_pantry_sess_guest_id   | (guest_session_id) WHERE NOT NULL |
|                          | idx_pantry_items_sess_id   | (pantry_session_id) — FK lookup   |
|                          | idx_pantry_items_canon_id  | (canonical_id) — Unconstrained FK |
|                          | idx_meal_plans_guest_id    | (guest_session_id) WHERE NOT NULL |
|                          | idx_meal_plan_slots_plan   | (plan_id) — FK lookup             |
|                          | idx_meal_plan_slots_rcp_id | (recipe_id) — External ID lookup  |
|                          | idx_shop_items_list_id     | (shopping_list_id) — FK lookup    |
|                          | idx_shop_items_category    | (shopping_list_id, category)      |
+──────────────────────────┴────────────────────────────┴───────────────────────────────────+
```

### 3.1 Lexical & Trigram Search Strategy
- **Stored TSVECTOR**: The `recipe_catalog.recipes.tsv_search` column is populated during ingestion using English stemming over recipe titles, descriptions, and tag sets:
  ```sql
  setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
  setweight(to_tsvector('english', COALESCE(description, '')), 'B')
  ```
- **GIN Indexing**: Query execution evaluates lexical matches using `tsv_search @@ plainto_tsquery('english', :query)`.
- **Trigram Similarity (`pg_trgm`)**: `idx_recipes_title_trgm` provides sub-string and typo-tolerant matching for recipe titles, prioritizing exact matches before falling back to trigram threshold rankings (`similarity(title, :query) > 0.3`).

---

## 4. Role Hierarchy & Least-Privilege Permissions

PostgreSQL enforces a capability-based grant model: permissions are denied unless explicitly granted. `database/004_permissions.sql` configures four distinct roles:

```
+───────────────────────────────+   Admin Role (DDL, Ingestion, Migrations)
|        foodflow_admin         |───► ALL PRIVILEGES on all 3 schemas & sequences
+───────────────────────────────+
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
+───────────+ +───────────+ +───────────+   Least-Privilege Service Roles
| profile   | | recipe    | | planner   |   • Usage only on dedicated schema
| _user     | | _user     | | _user     |   • Full DML on owned tables
+───────────+ +───────────+ +───────────+   • REVOKE ALL on other schemas
```

1. **`foodflow_profile_user`**:
   - `GRANT USAGE ON SCHEMA profile_nutrition`.
   - `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA profile_nutrition`.
   - `ALTER DEFAULT PRIVILEGES` configured both for the current executing user and explicitly `FOR ROLE foodflow_admin` on tables and sequences in `profile_nutrition`.
   - `REVOKE ALL PRIVILEGES` on `recipe_catalog` and `meal_planner`.
2. **`foodflow_recipe_user`**:
   - `GRANT USAGE ON SCHEMA recipe_catalog`.
   - `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA recipe_catalog`.
   - `ALTER DEFAULT PRIVILEGES` configured both for the current executing user and explicitly `FOR ROLE foodflow_admin` on tables and sequences in `recipe_catalog`.
   - `REVOKE ALL PRIVILEGES` on `profile_nutrition` and `meal_planner`.
3. **`foodflow_planner_user`**:
   - `GRANT USAGE ON SCHEMA meal_planner`.
   - `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA meal_planner`.
   - `ALTER DEFAULT PRIVILEGES` configured both for the current executing user and explicitly `FOR ROLE foodflow_admin` on tables and sequences in `meal_planner`.
   - `REVOKE ALL PRIVILEGES` on `profile_nutrition` and `recipe_catalog`.
4. **`foodflow_admin`**:
   - Privileged administrative account used **strictly for schema creation, Alembic migrations, and batch ingestion scripts**.
   - Not used by runtime microservices.
5. **Public Hardening**:
   - `REVOKE CREATE ON SCHEMA public FROM PUBLIC;`
   - Blocks service roles from creating tables in the public schema to prevent boundary bypasses.

---

## 5. SQL Execution Order

When deploying against a fresh PostgreSQL 16 database, execute the scripts sequentially:

```bash
# Executed as PostgreSQL superuser (e.g. postgres) or foodflow_admin:
psql -d foodflow_db -f database/001_create_schemas.sql
psql -d foodflow_db -f database/002_create_tables.sql
psql -d foodflow_db -f database/003_indexes.sql
psql -d foodflow_db -f database/004_permissions.sql
```

*Note on Idempotency*: `001` and `003` employ `IF NOT EXISTS` constructs. `002` defines clean table DDL wrapped in an explicit transaction (`BEGIN ... COMMIT`). Re-running `002` against an existing populated database requires standard migration tooling (Alembic) rather than raw script re-execution.

