-- ============================================================
-- NutriPod Database Index Definitions
-- File: 003_indexes.sql
-- Purpose: Performance indexing, foreign-key lookups, full-text,
--          trigram fuzzy search, and partial indexes.
-- Execution Order: 3 of 4
-- Target Engine: PostgreSQL 16
-- Run as: superuser (e.g. postgres) or foodflow_admin
-- Prerequisite: 001_create_schemas.sql, 002_create_tables.sql
-- ============================================================

-- Fresh execution semantics:
-- Creates indexes with IF NOT EXISTS to support idempotent initial runs.
-- All foreign key target columns and primary search query paths are indexed.
-- Note: UNIQUE constraints defined in 002_create_tables.sql (such as
-- uq_recipes_source on (source_dataset, source_id)) automatically generate
-- underlying unique B-tree indexes and are not duplicated here.

BEGIN;

-- ============================================================
-- 1. SCHEMA: profile_nutrition
-- ============================================================

-- USDA Food lookups
CREATE INDEX IF NOT EXISTS idx_usda_foods_data_type
    ON profile_nutrition.usda_foods (data_type);

CREATE INDEX IF NOT EXISTS idx_usda_foods_description_trgm
    ON profile_nutrition.usda_foods USING GIN (description gin_trgm_ops);

-- USDA Nutrients and Portions FK lookups
CREATE INDEX IF NOT EXISTS idx_usda_food_nutrients_fdc_id
    ON profile_nutrition.usda_food_nutrients (fdc_id);

CREATE INDEX IF NOT EXISTS idx_usda_food_nutrients_nutrient_id
    ON profile_nutrition.usda_food_nutrients (nutrient_id);

CREATE INDEX IF NOT EXISTS idx_usda_food_nutrients_composite
    ON profile_nutrition.usda_food_nutrients (fdc_id, nutrient_id);

CREATE INDEX IF NOT EXISTS idx_usda_food_portions_fdc_id
    ON profile_nutrition.usda_food_portions (fdc_id);

-- Nutrition estimates cache index
-- Facilitates fast status checks and batch retrieval
CREATE INDEX IF NOT EXISTS idx_nutrition_estimates_status
    ON profile_nutrition.nutrition_estimates (status);


-- ============================================================
-- 2. SCHEMA: recipe_catalog
-- ============================================================

-- Core full-text search: GIN index on stored tsv_search column
-- Ingestion pipelines populate tsv_search via setweight(to_tsvector('english', ...))
CREATE INDEX IF NOT EXISTS idx_recipes_tsv_search
    ON recipe_catalog.recipes USING GIN (tsv_search);

-- Trigram index on recipe title for fuzzy matching / autocomplete
CREATE INDEX IF NOT EXISTS idx_recipes_title_trgm
    ON recipe_catalog.recipes USING GIN (title gin_trgm_ops);

-- Dataset filtering index
CREATE INDEX IF NOT EXISTS idx_recipes_source_dataset
    ON recipe_catalog.recipes (source_dataset);

-- Partial indexes for faceted filtering (avoids indexing NULL rows)
CREATE INDEX IF NOT EXISTS idx_recipes_total_time_filtered
    ON recipe_catalog.recipes (total_time_minutes)
    WHERE total_time_minutes IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_recipes_cuisine_filtered
    ON recipe_catalog.recipes (cuisine)
    WHERE cuisine IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_recipes_servings_filtered
    ON recipe_catalog.recipes (servings)
    WHERE servings IS NOT NULL;

-- Recipe ingredients lookups
CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe_id
    ON recipe_catalog.recipe_ingredients (recipe_id);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_canonical_id
    ON recipe_catalog.recipe_ingredients (canonical_ingredient_id)
    WHERE canonical_ingredient_id IS NOT NULL;

-- Recipe instructions lookup
CREATE INDEX IF NOT EXISTS idx_recipe_instructions_recipe_id
    ON recipe_catalog.recipe_instructions (recipe_id);

-- Recipe tags lookups
CREATE INDEX IF NOT EXISTS idx_recipe_tags_recipe_id
    ON recipe_catalog.recipe_tags (recipe_id);

CREATE INDEX IF NOT EXISTS idx_recipe_tags_tag
    ON recipe_catalog.recipe_tags (tag);

-- Ratings sorting lookup (highest rated recipes first)
CREATE INDEX IF NOT EXISTS idx_recipe_ratings_ranking
    ON recipe_catalog.recipe_ratings (rating_average DESC NULLS LAST, rating_count DESC);

-- Canonical ingredients & synonyms search
CREATE INDEX IF NOT EXISTS idx_canonical_ingredients_category
    ON recipe_catalog.canonical_ingredients (category)
    WHERE category IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_canonical_ingredients_name_trgm
    ON recipe_catalog.canonical_ingredients USING GIN (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_ingredient_synonyms_canonical_id
    ON recipe_catalog.ingredient_synonyms (canonical_ingredient_id);

CREATE INDEX IF NOT EXISTS idx_ingredient_synonyms_synonym_trgm
    ON recipe_catalog.ingredient_synonyms USING GIN (synonym gin_trgm_ops);


-- ============================================================
-- 3. SCHEMA: meal_planner
-- ============================================================

-- Guest session expiry and activity lookups
CREATE INDEX IF NOT EXISTS idx_guest_sessions_expires_at
    ON meal_planner.guest_sessions (expires_at);

CREATE INDEX IF NOT EXISTS idx_guest_sessions_last_active
    ON meal_planner.guest_sessions (last_active_at);

-- Pantry session lookups
CREATE INDEX IF NOT EXISTS idx_pantry_sessions_guest_id
    ON meal_planner.pantry_sessions (guest_session_id)
    WHERE guest_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pantry_session_items_session_id
    ON meal_planner.pantry_session_items (pantry_session_id);

-- Unconstrained index on external canonical ingredient reference
-- Supports fast lookup when checking pantry overlap against recipes
CREATE INDEX IF NOT EXISTS idx_pantry_items_canonical_id
    ON meal_planner.pantry_session_items (canonical_ingredient_id)
    WHERE canonical_ingredient_id IS NOT NULL;

-- Meal plan lookups
CREATE INDEX IF NOT EXISTS idx_meal_plans_guest_id
    ON meal_planner.meal_plans (guest_session_id)
    WHERE guest_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_meal_plan_slots_plan_id
    ON meal_planner.meal_plan_slots (plan_id);

-- External recipe_id lookup on slots for tracking scheduling frequency
CREATE INDEX IF NOT EXISTS idx_meal_plan_slots_recipe_id
    ON meal_planner.meal_plan_slots (recipe_id);

-- Shopping list lookups
CREATE INDEX IF NOT EXISTS idx_shopping_list_items_list_id
    ON meal_planner.shopping_list_items (shopping_list_id);

CREATE INDEX IF NOT EXISTS idx_shopping_list_items_category
    ON meal_planner.shopping_list_items (shopping_list_id, category);

COMMIT;

