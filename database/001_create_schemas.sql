-- ============================================================
-- FoodFlow Database Bootstrap
-- File: 001_create_schemas.sql
-- Purpose: Create extensions, schemas, and database roles
-- Execution Order: 1 of 4
-- PostgreSQL 16
-- Run as superuser / foodflow_admin
-- ============================================================

-- ============================================================
-- SECURITY NOTICE
-- ============================================================
-- All role passwords are set to 'CHANGE_ME' as placeholders.
-- Before any deployment (including local development):
--   1. Replace passwords in .env or secrets management
--   2. Use ALTER ROLE ... PASSWORD '...' after creation
--   3. Never commit real passwords to version control
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- trigram similarity for fuzzy search

-- Schemas
CREATE SCHEMA IF NOT EXISTS profile_nutrition;
CREATE SCHEMA IF NOT EXISTS recipe_catalog;
CREATE SCHEMA IF NOT EXISTS meal_planner;

-- Roles (passwords must be supplied by the operator at runtime)
-- After running this file, immediately change passwords:
--   ALTER ROLE foodflow_profile_user WITH PASSWORD 'secure_password_here';
--   ALTER ROLE foodflow_recipe_user WITH PASSWORD 'secure_password_here';
--   ALTER ROLE foodflow_planner_user WITH PASSWORD 'secure_password_here';
--   ALTER ROLE foodflow_admin WITH PASSWORD 'secure_password_here';

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'foodflow_profile_user') THEN
        CREATE ROLE foodflow_profile_user WITH LOGIN PASSWORD 'CHANGE_ME';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'foodflow_recipe_user') THEN
        CREATE ROLE foodflow_recipe_user WITH LOGIN PASSWORD 'CHANGE_ME';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'foodflow_planner_user') THEN
        CREATE ROLE foodflow_planner_user WITH LOGIN PASSWORD 'CHANGE_ME';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'foodflow_admin') THEN
        CREATE ROLE foodflow_admin WITH LOGIN CREATEROLE PASSWORD 'CHANGE_ME';
    END IF;
END
$$;

COMMENT ON ROLE foodflow_profile_user IS 'Least-privilege role for Profile & Nutrition Service (port 8001). Access limited to profile_nutrition schema.';
COMMENT ON ROLE foodflow_recipe_user IS 'Least-privilege role for Recipe & Ingredient Service (port 8002). Access limited to recipe_catalog schema.';
COMMENT ON ROLE foodflow_planner_user IS 'Least-privilege role for Recommendation & Meal Planner Service (port 8003). Access limited to meal_planner schema.';
COMMENT ON ROLE foodflow_admin IS 'Privileged role for migrations, dataset ingestion, and schema DDL. NOT for application runtime.';
