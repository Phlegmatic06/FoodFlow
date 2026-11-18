"""Unit and integration test suite for NutriPod backend service foundations.

Tests verify:
- Service initialization and default configurations.
- OpenAPI health contracts and liveness probes.
- Live database readiness probes with restricted roles.
- Readiness failure handling (HTTP 503).
- Role enforcement and prevention of administrative credential usage.
- Strict schema isolation between microservices.
- Credential masking in URLs, logs, and error messages.
- Standardized error response structure.
"""

from __future__ import annotations

import logging
import os
import unittest
from unittest.mock import MagicMock, patch

import psycopg
from starlette.testclient import TestClient

from services.common.config import load_env_file, mask_database_url
from services.common.database import ServiceDatabaseManager
from services.common.logging import CredentialMaskingFilter
from services.common.models import DatabaseReadinessInfo
from services.profile_nutrition.config import settings as profile_settings
from services.profile_nutrition.main import app as profile_app
from services.recipe_ingredient.config import settings as recipe_settings
from services.recipe_ingredient.main import app as recipe_app
from services.recommendation_planner.config import settings as planner_settings
from services.recommendation_planner.main import app as planner_app

load_env_file()


class TestServiceConfiguration(unittest.TestCase):
    """Test configuration defaults and metadata for each microservice."""

    def test_profile_service_settings(self) -> None:
        self.assertEqual(profile_settings.service_name, "profile-nutrition")
        self.assertEqual(profile_settings.port, 8001)
        self.assertEqual(profile_settings.expected_db_role, "foodflow_profile_user")
        self.assertEqual(profile_settings.target_schema, "profile_nutrition")
        self.assertEqual(profile_settings.probe_table, "usda_foods")
        self.assertIsNotNone(profile_settings.database_url)

    def test_recipe_service_settings(self) -> None:
        self.assertEqual(recipe_settings.service_name, "recipe-ingredient")
        self.assertEqual(recipe_settings.port, 8002)
        self.assertEqual(recipe_settings.expected_db_role, "foodflow_recipe_user")
        self.assertEqual(recipe_settings.target_schema, "recipe_catalog")
        self.assertEqual(recipe_settings.probe_table, "recipes")
        self.assertIsNotNone(recipe_settings.database_url)

    def test_planner_service_settings(self) -> None:
        self.assertEqual(planner_settings.service_name, "recommendation-planner")
        self.assertEqual(planner_settings.port, 8003)
        self.assertEqual(planner_settings.expected_db_role, "foodflow_planner_user")
        self.assertEqual(planner_settings.target_schema, "meal_planner")
        self.assertEqual(planner_settings.probe_table, "guest_sessions")
        self.assertIsNotNone(planner_settings.database_url)


class TestCredentialMasking(unittest.TestCase):
    """Test credential sanitization in URLs, error messages, and log records."""

    def test_mask_database_url_with_credentials(self) -> None:
        url = "postgresql://my_user:secret_password_123@localhost:5432/my_db"
        masked = mask_database_url(url)
        self.assertNotIn("secret_password_123", masked)
        self.assertIn("my_user:********@localhost:5432/my_db", masked)

    def test_mask_database_url_without_credentials(self) -> None:
        url = "postgresql://localhost:5432/my_db"
        masked = mask_database_url(url)
        self.assertEqual(masked, url)

    def test_mask_database_url_empty_or_none(self) -> None:
        self.assertEqual(mask_database_url(None), "<NOT_SET>")
        self.assertEqual(mask_database_url(""), "<NOT_SET>")

    def test_credential_masking_filter(self) -> None:
        log_filter = CredentialMaskingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Connecting to postgresql://user:super_secret_pw@db.local:5432/foodflow",
            args=(),
            exc_info=None,
        )
        log_filter.filter(record)
        self.assertNotIn("super_secret_pw", record.msg)
        self.assertIn("user:********@db.local:5432/foodflow", record.msg)

    def test_database_manager_mask_error_message(self) -> None:
        raw_error = "FATAL: password authentication failed for user:secret_pass_abc@127.0.0.1:5432"
        masked = ServiceDatabaseManager.mask_error_message(raw_error)
        self.assertNotIn("secret_pass_abc", masked)
        self.assertIn(":********@", masked)


class TestHealthAndLivenessEndpoints(unittest.TestCase):
    """Test standard health check and orchestrator liveness endpoints."""

    def test_profile_health_and_liveness(self) -> None:
        with TestClient(profile_app) as client:
            resp_health = client.get("/health")
            self.assertEqual(resp_health.status_code, 200)
            self.assertEqual(
                resp_health.json(),
                {"status": "healthy", "service": "profile-nutrition", "version": "0.1.0"},
            )

            resp_live = client.get("/health/live")
            self.assertEqual(resp_live.status_code, 200)
            self.assertEqual(
                resp_live.json(),
                {"status": "healthy", "service": "profile-nutrition", "version": "0.1.0"},
            )

    def test_recipe_health_and_liveness(self) -> None:
        with TestClient(recipe_app) as client:
            resp_health = client.get("/health")
            self.assertEqual(resp_health.status_code, 200)
            self.assertEqual(
                resp_health.json(),
                {"status": "healthy", "service": "recipe-ingredient", "version": "0.1.0"},
            )

            resp_live = client.get("/health/live")
            self.assertEqual(resp_live.status_code, 200)
            self.assertEqual(
                resp_live.json(),
                {"status": "healthy", "service": "recipe-ingredient", "version": "0.1.0"},
            )

    def test_planner_health_and_liveness(self) -> None:
        with TestClient(planner_app) as client:
            resp_health = client.get("/health")
            self.assertEqual(resp_health.status_code, 200)
            self.assertEqual(
                resp_health.json(),
                {"status": "healthy", "service": "recommendation-planner", "version": "0.1.0"},
            )

            resp_live = client.get("/health/live")
            self.assertEqual(resp_live.status_code, 200)
            self.assertEqual(
                resp_live.json(),
                {"status": "healthy", "service": "recommendation-planner", "version": "0.1.0"},
            )


class TestReadinessEndpointsLiveDatabase(unittest.TestCase):
    """Test readiness endpoints against live PostgreSQL 16 container."""

    def test_profile_readiness_live_db(self) -> None:
        with TestClient(profile_app) as client:
            resp = client.get("/health/ready")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ready")
            self.assertEqual(data["service"], "profile-nutrition")
            self.assertEqual(data["version"], "0.1.0")
            db_info = data["database"]
            self.assertTrue(db_info["connected"])
            self.assertEqual(db_info["user"], "foodflow_profile_user")
            self.assertEqual(db_info["schema"], "profile_nutrition")
            self.assertEqual(db_info["database"], "foodflow_db")
            self.assertIsNone(db_info["error"])

    def test_recipe_readiness_live_db(self) -> None:
        with TestClient(recipe_app) as client:
            resp = client.get("/health/ready")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ready")
            self.assertEqual(data["service"], "recipe-ingredient")
            self.assertEqual(data["version"], "0.1.0")
            db_info = data["database"]
            self.assertTrue(db_info["connected"])
            self.assertEqual(db_info["user"], "foodflow_recipe_user")
            self.assertEqual(db_info["schema"], "recipe_catalog")
            self.assertEqual(db_info["database"], "foodflow_db")
            self.assertIsNone(db_info["error"])

    def test_planner_readiness_live_db(self) -> None:
        with TestClient(planner_app) as client:
            resp = client.get("/health/ready")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["status"], "ready")
            self.assertEqual(data["service"], "recommendation-planner")
            self.assertEqual(data["version"], "0.1.0")
            db_info = data["database"]
            self.assertTrue(db_info["connected"])
            self.assertEqual(db_info["user"], "foodflow_planner_user")
            self.assertEqual(db_info["schema"], "meal_planner")
            self.assertEqual(db_info["database"], "foodflow_db")
            self.assertIsNone(db_info["error"])


class TestReadinessFailureHandling(unittest.TestCase):
    """Test readiness probe behavior under database failure conditions."""

    def test_readiness_returns_503_when_database_fails(self) -> None:
        mock_db = MagicMock(spec=ServiceDatabaseManager)
        mock_db.check_readiness.return_value = DatabaseReadinessInfo(
            connected=False,
            user=None,
            schema_name="profile_nutrition",
            database=None,
            error="Connection refused on port 5432",
        )

        from services.profile_nutrition.database import get_db_manager

        profile_app.dependency_overrides[get_db_manager] = lambda: mock_db
        try:
            with TestClient(profile_app) as client:
                resp = client.get("/health/ready")
                self.assertEqual(resp.status_code, 503)
                data = resp.json()
                self.assertEqual(data["status"], "not_ready")
                self.assertEqual(data["service"], "profile-nutrition")
                self.assertFalse(data["database"]["connected"])
                self.assertEqual(data["database"]["error"], "Connection refused on port 5432")
        finally:
            profile_app.dependency_overrides.pop(get_db_manager, None)

    def test_readiness_when_dsn_is_none(self) -> None:
        mgr = ServiceDatabaseManager(
            service_name="test-service",
            expected_role="test_role",
            target_schema="test_schema",
            probe_table="test_table",
            dsn=None,
        )
        info = mgr.check_readiness()
        self.assertFalse(info.connected)
        self.assertIn("not configured", info.error or "")


class TestRoleEnforcementAndSchemaIsolation(unittest.TestCase):
    """Test role validation, administrative credential rejection, and schema isolation."""

    def test_rejection_of_admin_role_credentials(self) -> None:
        admin_url = os.environ.get("DATABASE_URL")
        self.assertIsNotNone(admin_url)

        mgr = ServiceDatabaseManager(
            service_name="profile-nutrition",
            expected_role="foodflow_profile_user",
            target_schema="profile_nutrition",
            probe_table="usda_foods",
            dsn=admin_url,
        )
        mgr.open()
        try:
            info = mgr.check_readiness()
            self.assertFalse(info.connected)
            self.assertIn("Security violation", info.error or "")
            self.assertIn("forbidden administrative role", info.error or "")
        finally:
            mgr.close()

    def test_role_mismatch_rejection(self) -> None:
        recipe_url = os.environ.get("RECIPE_SERVICE_DATABASE_URL")
        self.assertIsNotNone(recipe_url)

        # Configure manager expecting profile user but connecting with recipe user URL
        mgr = ServiceDatabaseManager(
            service_name="profile-nutrition",
            expected_role="foodflow_profile_user",
            target_schema="profile_nutrition",
            probe_table="usda_foods",
            dsn=recipe_url,
        )
        mgr.open()
        try:
            info = mgr.check_readiness()
            self.assertFalse(info.connected)
            self.assertIn("Role mismatch", info.error or "")
        finally:
            mgr.close()

    def test_profile_user_cannot_access_other_schemas(self) -> None:
        profile_url = os.environ.get("PROFILE_SERVICE_DATABASE_URL")
        self.assertIsNotNone(profile_url)

        with psycopg.connect(profile_url) as conn:
            with conn.cursor() as cur:
                # Allowed schema query
                cur.execute("SELECT COUNT(*) FROM profile_nutrition.usda_foods;")
                count = cur.fetchone()[0]
                self.assertGreater(count, 0)

                # Denied on recipe_catalog schema
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM recipe_catalog.recipes LIMIT 1;")

                conn.rollback()

                # Denied on meal_planner schema
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM meal_planner.guest_sessions LIMIT 1;")

    def test_recipe_user_cannot_access_other_schemas(self) -> None:
        recipe_url = os.environ.get("RECIPE_SERVICE_DATABASE_URL")
        self.assertIsNotNone(recipe_url)

        with psycopg.connect(recipe_url) as conn:
            with conn.cursor() as cur:
                # Allowed schema query
                cur.execute("SELECT COUNT(*) FROM recipe_catalog.recipes;")
                count = cur.fetchone()[0]
                self.assertGreater(count, 0)

                # Denied on profile_nutrition schema
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM profile_nutrition.usda_foods LIMIT 1;")

                conn.rollback()

                # Denied on meal_planner schema
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM meal_planner.guest_sessions LIMIT 1;")

    def test_planner_user_cannot_access_other_schemas(self) -> None:
        planner_url = os.environ.get("PLANNER_SERVICE_DATABASE_URL")
        self.assertIsNotNone(planner_url)

        with psycopg.connect(planner_url) as conn:
            with conn.cursor() as cur:
                # Allowed schema query
                cur.execute("SELECT COUNT(*) FROM meal_planner.guest_sessions;")
                count = cur.fetchone()[0]
                self.assertEqual(count, 0)

                # Denied on profile_nutrition schema
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM profile_nutrition.usda_foods LIMIT 1;")

                conn.rollback()

                # Denied on recipe_catalog schema
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM recipe_catalog.recipes LIMIT 1;")


class TestErrorResponseContract(unittest.TestCase):
    """Test standardized error responses conform to OpenAPI contract."""

    def test_not_found_error_structure(self) -> None:
        with TestClient(profile_app) as client:
            resp = client.get("/nonexistent/endpoint", headers={"X-Request-ID": "test_req_12345"})
            self.assertEqual(resp.status_code, 404)
            data = resp.json()
            self.assertIn("error", data)
            self.assertEqual(data["error"]["code"], "HTTP_404")
            self.assertEqual(data["error"]["message"], "Not Found")
            self.assertEqual(data["error"]["request_id"], "test_req_12345")
            self.assertEqual(resp.headers.get("X-Request-ID"), "test_req_12345")


class TestCORSConfiguration(unittest.TestCase):
    """Test CORS preflight, explicit headers, and credential isolation across all three microservices."""

    def test_cors_preflight_all_services(self) -> None:
        services = [
            ("profile", profile_app),
            ("recipe", recipe_app),
            ("planner", planner_app),
        ]
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,X-Request-ID,X-Guest-Session-ID",
        }
        for name, app in services:
            with self.subTest(service=name):
                with TestClient(app) as client:
                    resp = client.options("/api/v1/health", headers=headers)
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(resp.headers.get("access-control-allow-origin"), "http://localhost:5173")
                    self.assertIn("POST", resp.headers.get("access-control-allow-methods", ""))
                    # Verify credentials are NOT allowed by default
                    self.assertIsNone(resp.headers.get("access-control-allow-credentials"))
                    # Verify explicit allowed headers are returned
                    allowed_headers = resp.headers.get("access-control-allow-headers", "").lower()
                    self.assertIn("content-type", allowed_headers)
                    self.assertIn("x-request-id", allowed_headers)
                    self.assertIn("x-guest-session-id", allowed_headers)
                    self.assertNotEqual(allowed_headers.strip(), "*")

    def test_cors_disallowed_origin(self) -> None:
        headers = {
            "Origin": "http://evil-origin.example.com",
            "Access-Control-Request-Method": "GET",
        }
        with TestClient(profile_app) as client:
            resp = client.options("/api/v1/health", headers=headers)
            self.assertIsNone(resp.headers.get("access-control-allow-origin"))

    def test_cors_disallowed_header(self) -> None:
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Unauthorized-Secret-Header",
        }
        with TestClient(recipe_app) as client:
            resp = client.options("/api/v1/health", headers=headers)
            allowed = resp.headers.get("access-control-allow-headers", "")
            self.assertNotIn("x-unauthorized-secret-header", allowed.lower())


if __name__ == "__main__":
    unittest.main()

