-- ============================================================
-- FoodFlow Database Access Control & Least-Privilege Grants
-- File: 004_permissions.sql
-- Purpose: Schema-isolated role permissions, default privileges,
--          and cross-schema isolation enforcement.
-- Execution Order: 4 of 4
-- Target Engine: PostgreSQL 16
-- Run as: superuser (e.g. postgres) or foodflow_admin
-- Prerequisite: 001_create_schemas.sql, 002_create_tables.sql, 003_indexes.sql
-- ============================================================

-- PostgreSQL Authorization Model Note:
-- PostgreSQL uses a capability-based grant model: access is forbidden by default
-- unless explicitly permitted via GRANT. There is no explicit "DENY" keyword in
-- standard PostgreSQL SQL. Isolation is enforced by:
--   1. Granting USAGE and DML strictly to the dedicated service role for its schema.
--   2. Explicitly revoking default public permissions from the public schema.
--   3. Revoking any accidental cross-schema privileges.
--   4. Never making service roles members of other service roles.

BEGIN;

-- ============================================================
-- 0. HARDEN PUBLIC SCHEMA
-- Restrict standard public schema so application roles cannot
-- create arbitrary tables or bypass schema boundaries.
-- ============================================================
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM foodflow_profile_user, foodflow_recipe_user, foodflow_planner_user;


-- ============================================================
-- 1. SERVICE 1: Profile & Nutrition Service (Port 8001)
-- Role: foodflow_profile_user
-- Schema: profile_nutrition
-- ============================================================

-- Grant schema access
GRANT USAGE ON SCHEMA profile_nutrition TO foodflow_profile_user;

-- Grant table DML on profile_nutrition tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA profile_nutrition TO foodflow_profile_user;

-- Grant sequence access for identity and sequence columns
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA profile_nutrition TO foodflow_profile_user;

-- Ensure future tables and sequences created in profile_nutrition inherit these grants
-- Handles both objects created by current user and objects created by foodflow_admin during migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA profile_nutrition
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO foodflow_profile_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA profile_nutrition
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO foodflow_profile_user;

ALTER DEFAULT PRIVILEGES FOR ROLE foodflow_admin IN SCHEMA profile_nutrition
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO foodflow_profile_user;
ALTER DEFAULT PRIVILEGES FOR ROLE foodflow_admin IN SCHEMA profile_nutrition
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO foodflow_profile_user;

-- Enforce isolation: ensure profile service has NO permissions in other schemas
REVOKE ALL PRIVILEGES ON SCHEMA recipe_catalog FROM foodflow_profile_user;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA recipe_catalog FROM foodflow_profile_user;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA recipe_catalog FROM foodflow_profile_user;

REVOKE ALL PRIVILEGES ON SCHEMA meal_planner FROM foodflow_profile_user;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA meal_planner FROM foodflow_profile_user;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA meal_planner FROM foodflow_profile_user;


-- ============================================================
-- 2. SERVICE 2: Recipe & Ingredient Service (Port 8002)
-- Role: foodflow_recipe_user
-- Schema: recipe_catalog
-- ============================================================

-- Grant schema access
GRANT USAGE ON SCHEMA recipe_catalog TO foodflow_recipe_user;

-- Grant table DML on recipe_catalog tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA recipe_catalog TO foodflow_recipe_user;

-- Grant sequence access for identity and sequence columns
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA recipe_catalog TO foodflow_recipe_user;

-- Ensure future tables and sequences created in recipe_catalog inherit these grants
-- Handles both objects created by current user and objects created by foodflow_admin during migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA recipe_catalog
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO foodflow_recipe_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA recipe_catalog
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO foodflow_recipe_user;

ALTER DEFAULT PRIVILEGES FOR ROLE foodflow_admin IN SCHEMA recipe_catalog
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO foodflow_recipe_user;
ALTER DEFAULT PRIVILEGES FOR ROLE foodflow_admin IN SCHEMA recipe_catalog
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO foodflow_recipe_user;

-- Enforce isolation: ensure recipe service has NO permissions in other schemas
REVOKE ALL PRIVILEGES ON SCHEMA profile_nutrition FROM foodflow_recipe_user;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA profile_nutrition FROM foodflow_recipe_user;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA profile_nutrition FROM foodflow_recipe_user;

REVOKE ALL PRIVILEGES ON SCHEMA meal_planner FROM foodflow_recipe_user;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA meal_planner FROM foodflow_recipe_user;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA meal_planner FROM foodflow_recipe_user;


-- ============================================================
-- 3. SERVICE 3: Recommendation & Meal Planner Service (Port 8003)
-- Role: foodflow_planner_user
-- Schema: meal_planner
-- ============================================================

-- Grant schema access
GRANT USAGE ON SCHEMA meal_planner TO foodflow_planner_user;

-- Grant table DML on meal_planner tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA meal_planner TO foodflow_planner_user;

-- Grant sequence access for identity and sequence columns
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA meal_planner TO foodflow_planner_user;

-- Ensure future tables and sequences created in meal_planner inherit these grants
-- Handles both objects created by current user and objects created by foodflow_admin during migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA meal_planner
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO foodflow_planner_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA meal_planner
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO foodflow_planner_user;

ALTER DEFAULT PRIVILEGES FOR ROLE foodflow_admin IN SCHEMA meal_planner
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO foodflow_planner_user;
ALTER DEFAULT PRIVILEGES FOR ROLE foodflow_admin IN SCHEMA meal_planner
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO foodflow_planner_user;

-- Enforce isolation: ensure planner service has NO permissions in other schemas
REVOKE ALL PRIVILEGES ON SCHEMA profile_nutrition FROM foodflow_planner_user;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA profile_nutrition FROM foodflow_planner_user;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA profile_nutrition FROM foodflow_planner_user;

REVOKE ALL PRIVILEGES ON SCHEMA recipe_catalog FROM foodflow_planner_user;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA recipe_catalog FROM foodflow_planner_user;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA recipe_catalog FROM foodflow_planner_user;


-- ============================================================
-- 4. ADMINISTRATIVE & MIGRATION ROLE: foodflow_admin
-- Role: foodflow_admin
-- Schemas: profile_nutrition, recipe_catalog, meal_planner
-- ============================================================

-- Grant comprehensive schema and DDL/DML access across all three application schemas
GRANT ALL PRIVILEGES ON SCHEMA profile_nutrition TO foodflow_admin;
GRANT ALL PRIVILEGES ON SCHEMA recipe_catalog TO foodflow_admin;
GRANT ALL PRIVILEGES ON SCHEMA meal_planner TO foodflow_admin;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA profile_nutrition TO foodflow_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA recipe_catalog TO foodflow_admin;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA meal_planner TO foodflow_admin;

GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA profile_nutrition TO foodflow_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA recipe_catalog TO foodflow_admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA meal_planner TO foodflow_admin;

-- Configure default privileges for objects created by foodflow_admin
ALTER DEFAULT PRIVILEGES IN SCHEMA profile_nutrition
    GRANT ALL PRIVILEGES ON TABLES TO foodflow_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA profile_nutrition
    GRANT ALL PRIVILEGES ON SEQUENCES TO foodflow_admin;

ALTER DEFAULT PRIVILEGES IN SCHEMA recipe_catalog
    GRANT ALL PRIVILEGES ON TABLES TO foodflow_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA recipe_catalog
    GRANT ALL PRIVILEGES ON SEQUENCES TO foodflow_admin;

ALTER DEFAULT PRIVILEGES IN SCHEMA meal_planner
    GRANT ALL PRIVILEGES ON TABLES TO foodflow_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA meal_planner
    GRANT ALL PRIVILEGES ON SEQUENCES TO foodflow_admin;

COMMIT;

