-- ============================================================
-- FoodFlow Migration: 005_add_recipenlg_source_origin.sql
-- Purpose: Add source_origin column to recipe_catalog.recipes to
--          track RecipeNLG sub-corpus origin ('Gathered' or 'Recipes1M').
-- Safety:  Additive migration. Column is NULLable, preserving all
--          existing Food.com records with zero downtime or data loss.
-- Execution: Apply using foodflow_admin role.
-- ============================================================

-- Step 1: Add nullable column source_origin
ALTER TABLE recipe_catalog.recipes
ADD COLUMN IF NOT EXISTS source_origin VARCHAR(32);

-- Step 2: Add check constraint enforcing valid source values while allowing NULL
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

-- Step 3: Add documentation comment
COMMENT ON COLUMN recipe_catalog.recipes.source_origin IS
    'Origin sub-corpus for RecipeNLG recipes (Gathered or Recipes1M). NULL for Food.com records.';

