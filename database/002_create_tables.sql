-- ============================================================
-- FoodFlow Database Schema Definitions
-- File: 002_create_tables.sql
-- Purpose: Table creation, constraints, and relationships
-- Execution Order: 2 of 4
-- Target Engine: PostgreSQL 16
-- Run as: superuser (e.g. postgres) or foodflow_admin
-- Prerequisite: 001_create_schemas.sql
-- ============================================================

-- Fresh execution semantics:
-- This script creates tables across profile_nutrition, recipe_catalog, and meal_planner.
-- All table creation statements use standard relational constraints.
-- Re-running against an existing schema with drift requires explicit migration scripts.

BEGIN;

-- ============================================================
-- SCHEMA 1: profile_nutrition
-- Service Owner: Profile & Nutrition Service (Member 1, Port 8001)
-- Description: USDA FoodData Central nutritional repository and
--              recipe nutritional estimation cache.
-- ============================================================

-- Table: profile_nutrition.usda_foods
-- Source: USDA FoodData Central (food.csv)
CREATE TABLE profile_nutrition.usda_foods (
    fdc_id INTEGER PRIMARY KEY,
    data_type VARCHAR(32) NOT NULL,
    description TEXT NOT NULL,
    food_category_id INTEGER,
    publication_date DATE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE profile_nutrition.usda_foods IS
    'Core food items imported from USDA FoodData Central. fdc_id is the authoritative USDA identifier.';
COMMENT ON COLUMN profile_nutrition.usda_foods.fdc_id IS
    'Authoritative USDA FoodData Central unique integer identifier.';
COMMENT ON COLUMN profile_nutrition.usda_foods.data_type IS
    'USDA dataset category (e.g., foundation_food, sr_legacy_food, survey_fndds_food).';

-- Table: profile_nutrition.usda_nutrients
-- Source: USDA FoodData Central (nutrient.csv)
CREATE TABLE profile_nutrition.usda_nutrients (
    id INTEGER PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    unit_name VARCHAR(16) NOT NULL,
    nutrient_nbr VARCHAR(16),
    rank NUMERIC(8, 2)
);

COMMENT ON TABLE profile_nutrition.usda_nutrients IS
    'Nutrient definitions from USDA FoodData Central (e.g., Protein, Energy, Calcium).';
COMMENT ON COLUMN profile_nutrition.usda_nutrients.unit_name IS
    'Measurement unit specified by USDA (e.g., G, MG, UG, KCAL).';

-- Table: profile_nutrition.usda_food_nutrients
-- Source: USDA FoodData Central (food_nutrient.csv)
CREATE TABLE profile_nutrition.usda_food_nutrients (
    id INTEGER PRIMARY KEY,
    fdc_id INTEGER NOT NULL REFERENCES profile_nutrition.usda_foods(fdc_id) ON DELETE CASCADE,
    nutrient_id INTEGER NOT NULL REFERENCES profile_nutrition.usda_nutrients(id) ON DELETE RESTRICT,
    amount NUMERIC(12, 4),
    data_points INTEGER,
    derivation_id INTEGER
);

COMMENT ON TABLE profile_nutrition.usda_food_nutrients IS
    'Measured nutrient values per 100g of edible food portion from USDA FDC.';
COMMENT ON COLUMN profile_nutrition.usda_food_nutrients.amount IS
    'Nutrient amount per 100 grams of edible portion. NULL if unmeasured.';

-- Table: profile_nutrition.usda_food_portions
-- Source: USDA FoodData Central (food_portion.csv)
CREATE TABLE profile_nutrition.usda_food_portions (
    id INTEGER PRIMARY KEY,
    fdc_id INTEGER NOT NULL REFERENCES profile_nutrition.usda_foods(fdc_id) ON DELETE CASCADE,
    seq_num INTEGER,
    amount NUMERIC(8, 3),
    measure_unit_id INTEGER,
    portion_description VARCHAR(255),
    modifier VARCHAR(128),
    gram_weight NUMERIC(10, 3) NOT NULL
);

COMMENT ON TABLE profile_nutrition.usda_food_portions IS
    'Household serving portions and corresponding gram weights from USDA FoodData Central.';
COMMENT ON COLUMN profile_nutrition.usda_food_portions.gram_weight IS
    'Gram weight equivalent of the specified household portion.';

-- Table: profile_nutrition.nutrition_estimates
-- Purpose: Cached nutritional calculations and approximations for recipes.
-- Isolation boundary: recipe_id is a plain VARCHAR(64) reference with NO foreign key
-- to recipe_catalog.recipes. Resolved across services via REST API calls.
CREATE TABLE profile_nutrition.nutrition_estimates (
    recipe_id VARCHAR(64) PRIMARY KEY,
    status VARCHAR(32) NOT NULL CHECK (status IN ('calculated', 'uncalculated', 'reported_approximate')),
    calories_kcal NUMERIC(10, 2),
    total_fat_g NUMERIC(8, 2),
    saturated_fat_g NUMERIC(8, 2),
    carbohydrates_g NUMERIC(8, 2),
    sugar_g NUMERIC(8, 2),
    protein_g NUMERIC(8, 2),
    sodium_mg NUMERIC(8, 2),
    fiber_g NUMERIC(8, 2),
    ingredient_coverage_pct NUMERIC(5, 2),
    mapped_ingredient_count INTEGER,
    total_ingredient_count INTEGER,
    servings INTEGER,
    provenance_note TEXT,
    calculated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE profile_nutrition.nutrition_estimates IS
    'Calculated nutritional profiles and cached estimations for recipes. recipe_id is an external identifier with no database-level FK.';
COMMENT ON COLUMN profile_nutrition.nutrition_estimates.recipe_id IS
    'External recipe reference (e.g. rcp_foodcom_5421). No cross-schema FK; resolved via Recipe Service REST API.';
COMMENT ON COLUMN profile_nutrition.nutrition_estimates.status IS
    'Calculation provenance status: calculated (USDA mapping >= 80%), reported_approximate (Food.com PDV), uncalculated (insufficient data).';

-- Table: profile_nutrition.ingestion_provenance
-- Purpose: Provenance and audit log for USDA dataset imports.
CREATE TABLE profile_nutrition.ingestion_provenance (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_dataset VARCHAR(32) NOT NULL,
    source_url TEXT NOT NULL,
    download_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    dataset_version VARCHAR(64),
    file_name VARCHAR(255) NOT NULL,
    file_sha256_checksum VARCHAR(64) NOT NULL,
    original_raw_row_count INTEGER,
    imported_row_count INTEGER,
    skipped_malformed_count INTEGER NOT NULL DEFAULT 0,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ingested_by VARCHAR(64) NOT NULL DEFAULT CURRENT_USER,
    notes TEXT
);

COMMENT ON TABLE profile_nutrition.ingestion_provenance IS
    'Audit record of USDA raw dataset downloads, checksums, and import row metrics.';


-- ============================================================
-- SCHEMA 2: recipe_catalog
-- Service Owner: Recipe & Ingredient Service (Member 2, Port 8002)
-- Description: Unified recipe repository, ingredient taxonomy,
--              ratings, and raw source nutrition values.
-- ============================================================

-- Table: recipe_catalog.canonical_ingredients
-- Purpose: Normalized ingredient taxonomy for pantry matching and search.
CREATE TABLE recipe_catalog.canonical_ingredients (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(64),
    is_pantry_staple BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_canonical_ingredients_name UNIQUE (name)
);

COMMENT ON TABLE recipe_catalog.canonical_ingredients IS
    'Authoritative normalized ingredient dictionary used for normalization and pantry match scoring.';
COMMENT ON COLUMN recipe_catalog.canonical_ingredients.is_pantry_staple IS
    'Indicates common household staple (e.g., salt, water, black pepper) that can be excluded from missing ingredient tallies.';

-- Table: recipe_catalog.ingredient_synonyms
-- Purpose: Mapping raw terminology variants to canonical ingredient records.
CREATE TABLE recipe_catalog.ingredient_synonyms (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    synonym VARCHAR(255) NOT NULL,
    canonical_ingredient_id INTEGER NOT NULL REFERENCES recipe_catalog.canonical_ingredients(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_ingredient_synonyms_synonym UNIQUE (synonym)
);

COMMENT ON TABLE recipe_catalog.ingredient_synonyms IS
    'Variant names, misspellings, and lexical synonyms resolving to canonical ingredients.';

-- Table: recipe_catalog.recipes
-- Purpose: Unified core catalogue for Food.com and RecipeNLG recipes.
CREATE TABLE recipe_catalog.recipes (
    id VARCHAR(64) PRIMARY KEY,
    source_dataset VARCHAR(32) NOT NULL,
    source_id VARCHAR(64) NOT NULL,
    title VARCHAR(512) NOT NULL,
    description TEXT,
    prep_time_minutes INTEGER CHECK (prep_time_minutes >= 0),
    cook_time_minutes INTEGER CHECK (cook_time_minutes >= 0),
    total_time_minutes INTEGER CHECK (total_time_minutes >= 0),
    servings INTEGER CHECK (servings > 0),
    cuisine VARCHAR(64),
    source_url TEXT,
    submitted_date DATE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    tsv_search TSVECTOR,
    CONSTRAINT uq_recipes_source UNIQUE (source_dataset, source_id)
);

COMMENT ON TABLE recipe_catalog.recipes IS
    'Unified recipe catalog aggregating Food.com and RecipeNLG datasets under rcp_{dataset}_{id} identifiers.';
COMMENT ON COLUMN recipe_catalog.recipes.id IS
    'Prefixed unified ID (e.g. rcp_foodcom_5421, rcp_nlg_108294). Authoritative global identifier across FoodFlow.';
COMMENT ON COLUMN recipe_catalog.recipes.servings IS
    'Servings yield. Explicitly NULL for RecipeNLG records where serving yield was not published. No artificial default.';
COMMENT ON COLUMN recipe_catalog.recipes.tsv_search IS
    'Full-text search vector over recipe title, description, and tags. Maintained by ingestion pipeline or database triggers.';

-- Table: recipe_catalog.recipe_ingredients
-- Purpose: Ordered ingredient entries per recipe, retaining raw text and optional canonical link.
CREATE TABLE recipe_catalog.recipe_ingredients (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipe_id VARCHAR(64) NOT NULL REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE,
    position SMALLINT NOT NULL,
    raw_text TEXT NOT NULL,
    canonical_ingredient_id INTEGER REFERENCES recipe_catalog.canonical_ingredients(id) ON DELETE SET NULL,
    quantity NUMERIC(10, 3),
    unit VARCHAR(32),
    CONSTRAINT uq_recipe_ingredients_pos UNIQUE (recipe_id, position)
);

COMMENT ON TABLE recipe_catalog.recipe_ingredients IS
    'Individual ingredients per recipe, preserving the original unparsed string and optional parsed quantity/unit.';
COMMENT ON COLUMN recipe_catalog.recipe_ingredients.raw_text IS
    'Original unmodified ingredient string from the source dataset.';
COMMENT ON COLUMN recipe_catalog.recipe_ingredients.canonical_ingredient_id IS
    'Internal foreign key to canonical_ingredients. NULL if unmapped or unparseable.';

-- Table: recipe_catalog.recipe_instructions
-- Purpose: Sequential preparation instructions per recipe.
CREATE TABLE recipe_catalog.recipe_instructions (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipe_id VARCHAR(64) NOT NULL REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE,
    step_number SMALLINT NOT NULL,
    instruction TEXT NOT NULL,
    CONSTRAINT uq_recipe_instructions_step UNIQUE (recipe_id, step_number)
);

COMMENT ON TABLE recipe_catalog.recipe_instructions IS
    'Sequential preparation steps per recipe. Original text preserved without algorithmic rewriting.';

-- Table: recipe_catalog.recipe_tags
-- Purpose: Categorical, dietary, and culinary tags associated with recipes.
CREATE TABLE recipe_catalog.recipe_tags (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipe_id VARCHAR(64) NOT NULL REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE,
    tag VARCHAR(128) NOT NULL,
    CONSTRAINT uq_recipe_tags_recipe_tag UNIQUE (recipe_id, tag)
);

COMMENT ON TABLE recipe_catalog.recipe_tags IS
    'Normalized lowercase tags for cuisine, dietary flags, meal courses, and occasion categories.';

-- Table: recipe_catalog.recipe_ratings
-- Purpose: Aggregated ratings derived from Food.com interaction records.
CREATE TABLE recipe_catalog.recipe_ratings (
    recipe_id VARCHAR(64) PRIMARY KEY REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE,
    rating_average NUMERIC(3, 2) CHECK (rating_average >= 0.0 AND rating_average <= 5.0),
    rating_count INTEGER NOT NULL DEFAULT 0 CHECK (rating_count >= 0),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE recipe_catalog.recipe_ratings IS
    'Aggregated review metrics. Unrated recipes (including all RecipeNLG records) have rating_average as NULL and rating_count as 0.';
COMMENT ON COLUMN recipe_catalog.recipe_ratings.rating_average IS
    'Average star rating (1.00 to 5.00). NULL if no reviews exist. Never fabricated.';

-- Table: recipe_catalog.recipe_nutrition_raw
-- Purpose: Original reported nutrition values from Food.com (RAW_recipes.csv).
-- Note: Food.com provides calories in kcal and six percentage daily values (%DV).
-- They are preserved verbatim as %DV. No silent conversion to grams occurs here.
CREATE TABLE recipe_catalog.recipe_nutrition_raw (
    recipe_id VARCHAR(64) PRIMARY KEY REFERENCES recipe_catalog.recipes(id) ON DELETE CASCADE,
    raw_calories NUMERIC(10, 2) NOT NULL,
    raw_total_fat_pdv NUMERIC(8, 2),
    raw_sugar_pdv NUMERIC(8, 2),
    raw_sodium_pdv NUMERIC(8, 2),
    raw_protein_pdv NUMERIC(8, 2),
    raw_saturated_fat_pdv NUMERIC(8, 2),
    raw_carbohydrates_pdv NUMERIC(8, 2)
);

COMMENT ON TABLE recipe_catalog.recipe_nutrition_raw IS
    'Raw reported nutrition metrics from Food.com. Preserves original percentage Daily Values (%DV). Gram conversions must be computed explicitly by consuming applications and marked as approximations.';
COMMENT ON COLUMN recipe_catalog.recipe_nutrition_raw.raw_calories IS
    'Reported energy content in kilocalories (kcal).';
COMMENT ON COLUMN recipe_catalog.recipe_nutrition_raw.raw_total_fat_pdv IS
    'Percentage Daily Value (%DV) for total fat based on FDA reference diet.';
COMMENT ON COLUMN recipe_catalog.recipe_nutrition_raw.raw_sugar_pdv IS
    'Percentage Daily Value (%DV) for sugar as reported in Food.com. No standard pre-2020 FDA reference exists; do not convert via generated columns.';

-- Table: recipe_catalog.ingestion_provenance
-- Purpose: Provenance and audit log for recipe catalogue imports.
CREATE TABLE recipe_catalog.ingestion_provenance (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_dataset VARCHAR(32) NOT NULL,
    source_url TEXT NOT NULL,
    download_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    dataset_version VARCHAR(64),
    file_name VARCHAR(255) NOT NULL,
    file_sha256_checksum VARCHAR(64) NOT NULL,
    original_raw_row_count INTEGER,
    imported_row_count INTEGER,
    skipped_malformed_count INTEGER NOT NULL DEFAULT 0,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ingested_by VARCHAR(64) NOT NULL DEFAULT CURRENT_USER,
    notes TEXT
);

COMMENT ON TABLE recipe_catalog.ingestion_provenance IS
    'Audit record of Food.com and RecipeNLG dataset ingestions, SHA-256 checksums, and row tallies.';


-- ============================================================
-- SCHEMA 3: meal_planner
-- Service Owner: Recommendation & Meal Planner Service (Member 3, Port 8003)
-- Description: Guest-first pantry sessions, meal planning schedules,
--              cooking execution progress, and consolidated grocery lists.
-- ============================================================

-- Table: meal_planner.guest_sessions
-- Purpose: Anonymous, lightweight guest sessions identified by UUID.
CREATE TABLE meal_planner.guest_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_active_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE meal_planner.guest_sessions IS
    'Anonymous guest session tokens stored client-side. Enables pantry matching and meal planning without mandatory user registration.';
COMMENT ON COLUMN meal_planner.guest_sessions.expires_at IS
    'Session expiration boundary (default 30 days from creation/activity). Inactive guest state is subject to purge.';

-- Table: meal_planner.pantry_sessions
-- Purpose: Active pantry inventory associated with a guest or anonymous session.
CREATE TABLE meal_planner.pantry_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_session_id UUID REFERENCES meal_planner.guest_sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE meal_planner.pantry_sessions IS
    'Pantry state instances tracking a collection of ingredients currently in a user inventory.';

-- Table: meal_planner.pantry_session_items
-- Purpose: Ingredients within a pantry session.
-- Isolation boundary: canonical_ingredient_id is a plain INTEGER reference with
-- NO foreign key to recipe_catalog.canonical_ingredients. Resolved via Recipe Service REST API.
CREATE TABLE meal_planner.pantry_session_items (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pantry_session_id UUID NOT NULL REFERENCES meal_planner.pantry_sessions(id) ON DELETE CASCADE,
    canonical_ingredient_id INTEGER,
    raw_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pantry_session_items_raw UNIQUE (pantry_session_id, raw_name)
);

COMMENT ON TABLE meal_planner.pantry_session_items IS
    'Items contained in a pantry session. canonical_ingredient_id stores Recipe Service IDs without cross-schema foreign keys.';
COMMENT ON COLUMN meal_planner.pantry_session_items.canonical_ingredient_id IS
    'External reference to recipe_catalog.canonical_ingredients.id. Resolved via Recipe Service REST normalization endpoint.';

-- Table: meal_planner.meal_plans
-- Purpose: Multi-day meal planning container.
CREATE TABLE meal_planner.meal_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    guest_session_id UUID REFERENCES meal_planner.guest_sessions(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL DEFAULT 'My Meal Plan',
    target_calories_kcal INTEGER CHECK (target_calories_kcal > 0),
    days SMALLINT NOT NULL DEFAULT 1 CHECK (days >= 1 AND days <= 14),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE meal_planner.meal_plans IS
    'User meal plan container spanning 1 to 14 days, optionally constrained by target daily calories.';

-- Table: meal_planner.meal_plan_slots
-- Purpose: Scheduled recipe allocation across days and meal times,
--          incorporating cooking status directly to eliminate redundant progress tables.
-- Isolation boundary: recipe_id is a plain VARCHAR(64) reference with NO foreign key
-- to recipe_catalog.recipes. Resolved via Recipe Service REST API.
CREATE TABLE meal_planner.meal_plan_slots (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plan_id UUID NOT NULL REFERENCES meal_planner.meal_plans(id) ON DELETE CASCADE,
    day_index SMALLINT NOT NULL CHECK (day_index >= 0),
    slot_type VARCHAR(16) NOT NULL CHECK (slot_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    recipe_id VARCHAR(64) NOT NULL,
    recipe_title VARCHAR(512) NOT NULL,
    cooking_status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (cooking_status IN ('pending', 'cooked', 'skipped')),
    status_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_meal_plan_slots_entry UNIQUE (plan_id, day_index, slot_type, recipe_id)
);

COMMENT ON TABLE meal_planner.meal_plan_slots IS
    'Scheduled meal slots. recipe_id is an external identifier resolved via REST. Cooking state is managed directly via cooking_status.';
COMMENT ON COLUMN meal_planner.meal_plan_slots.recipe_id IS
    'External recipe reference (e.g. rcp_foodcom_5421). No database foreign key to recipe_catalog.recipes.';
COMMENT ON COLUMN meal_planner.meal_plan_slots.recipe_title IS
    'Denormalized snapshot of recipe title at scheduling time for offline display.';
COMMENT ON COLUMN meal_planner.meal_plan_slots.cooking_status IS
    'Execution state for the slot: pending, cooked, or skipped.';

-- Table: meal_planner.shopping_lists
-- Purpose: Grocery shopping list generated from planned meals.
CREATE TABLE meal_planner.shopping_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES meal_planner.meal_plans(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_shopping_lists_plan UNIQUE (plan_id)
);

COMMENT ON TABLE meal_planner.shopping_lists IS
    'Consolidated shopping list tied to a specific meal plan (1:1 relationship).';

-- Table: meal_planner.shopping_list_items
-- Purpose: Individual ingredient line items in a shopping list.
CREATE TABLE meal_planner.shopping_list_items (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    shopping_list_id UUID NOT NULL REFERENCES meal_planner.shopping_lists(id) ON DELETE CASCADE,
    ingredient_name VARCHAR(255) NOT NULL,
    quantity_display VARCHAR(64),
    category VARCHAR(64),
    checked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE meal_planner.shopping_list_items IS
    'Checklist items grouped by supermarket category (e.g. Produce, Dairy, Pantry Staples).';
COMMENT ON COLUMN meal_planner.shopping_list_items.checked IS
    'Tracks procurement status during grocery shopping.';

COMMIT;

