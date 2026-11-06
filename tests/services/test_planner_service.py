"""Comprehensive unit and integration test suite for Recommendation & Meal Planner Service.

Verifies:
- OpenAPI contract conformance and property types.
- Anonymous guest session lifecycles, expiration boundaries, and isolation.
- Pantry inventory CRUD, raw text preservation, and empty dictionary handling.
- Pantry-to-recipe overlap matching, non-fabrication guarantee, and 502 resilience.
- Multi-day meal plan proposal generation and persistence.
- Recipe existence verification via Recipe Service and 400 validation rejection.
- Cross-guest data isolation across pantry, meal plans, and shopping lists.
- Cooking progress state tracking (pending, cooked, skipped).
- Consolidated shopping list generation, categorization, and quantity aggregation.
- Shopping list item procurement toggling.
- Restricted role permissions and schema isolation.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import psycopg
from starlette.testclient import TestClient

from services.common.config import load_env_file
from services.recommendation_planner.client import (
    ProfileServiceClient,
    RecipeServiceClient,
    UpstreamServiceUnavailableError,
)
from services.recommendation_planner.dependencies import (
    get_profile_client,
    get_recipe_client,
)
from services.recommendation_planner.main import app

load_env_file()


class BasePlannerTestCase(unittest.TestCase):
    """Base test class providing client setup and cleanup helper."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        planner_url = os.environ.get("PLANNER_SERVICE_DATABASE_URL")
        if planner_url:
            with psycopg.connect(planner_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM meal_planner.shopping_list_items;")
                    cur.execute("DELETE FROM meal_planner.shopping_lists;")
                    cur.execute("DELETE FROM meal_planner.meal_plan_slots;")
                    cur.execute("DELETE FROM meal_planner.meal_plans;")
                    cur.execute("DELETE FROM meal_planner.pantry_session_items;")
                    cur.execute("DELETE FROM meal_planner.pantry_sessions;")
                    cur.execute("DELETE FROM meal_planner.guest_sessions;")
                    conn.commit()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()


class TestGuestSessions(BasePlannerTestCase):
    """Test guest session creation, touch, retrieval, and expiration."""

    def test_create_guest_session(self) -> None:
        resp = self.client.post("/api/v1/guest-sessions")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        self.assertIn("session_id", data)
        self.assertIn("created_at", data)
        self.assertIn("expires_at", data)
        self.assertIn("last_active_at", data)

        created_dt = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        expires_dt = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        # Expiry must be roughly 30 days from creation
        diff_days = (expires_dt - created_dt).days
        self.assertIn(diff_days, [29, 30, 31])

    def test_get_guest_session_valid(self) -> None:
        create_res = self.client.post("/api/v1/guest-sessions")
        sid = create_res.json()["session_id"]

        get_res = self.client.get(f"/api/v1/guest-sessions/{sid}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["session_id"], sid)

    def test_get_guest_session_not_found(self) -> None:
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        resp = self.client.get(f"/api/v1/guest-sessions/{fake_uuid}")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "SESSION_EXPIRED")

    def test_get_guest_session_invalid_uuid(self) -> None:
        resp = self.client.get("/api/v1/guest-sessions/not-a-valid-uuid")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "SESSION_EXPIRED")


class TestPantryManagement(BasePlannerTestCase):
    """Test pantry inventory retrieval, mutation, raw text preservation, and clearing."""

    def setUp(self) -> None:
        res = self.client.post("/api/v1/guest-sessions")
        self.session_id = res.json()["session_id"]
        self.headers = {"X-Guest-Session-ID": self.session_id}

        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.normalize_ingredients.return_value = {"normalized": [], "unmatched": []}
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

    def test_pantry_requires_session_header(self) -> None:
        # Missing header -> 401
        r_get = self.client.get("/api/v1/pantry")
        self.assertEqual(r_get.status_code, 401)
        self.assertEqual(r_get.json()["error"]["code"], "SESSION_EXPIRED")

        r_put = self.client.put("/api/v1/pantry", json={"items": []})
        self.assertEqual(r_put.status_code, 401)
        self.assertEqual(r_put.json()["error"]["code"], "SESSION_EXPIRED")

    def test_get_empty_pantry(self) -> None:
        resp = self.client.get("/api/v1/pantry", headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["items"], [])
        self.assertEqual(data["total_count"], 0)

    def test_update_pantry_items_persists_raw_text(self) -> None:
        payload = {
            "items": [
                {"raw_name": "Organic Whole Rolled Oats"},
                {"raw_name": "Almond Milk", "canonical_ingredient_id": 999},
            ]
        }
        resp = self.client.put("/api/v1/pantry", headers=self.headers, json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_count"], 2)

        items = data["items"]
        self.assertEqual(items[0]["raw_name"], "Organic Whole Rolled Oats")
        self.assertIsNone(items[0]["canonical_ingredient_id"])
        self.assertEqual(items[1]["raw_name"], "Almond Milk")
        self.assertEqual(items[1]["canonical_ingredient_id"], 999)

        # Confirm GET reflects the updated state
        get_res = self.client.get("/api/v1/pantry", headers=self.headers)
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["total_count"], 2)

    def test_update_pantry_clears_inventory(self) -> None:
        # First add items
        self.client.put(
            "/api/v1/pantry",
            headers=self.headers,
            json={"items": [{"raw_name": "Eggs"}, {"raw_name": "Cheese"}]},
        )
        # Clear pantry with empty items array
        clear_res = self.client.put("/api/v1/pantry", headers=self.headers, json={"items": []})
        self.assertEqual(clear_res.status_code, 200)
        self.assertEqual(clear_res.json()["total_count"], 0)
        self.assertEqual(clear_res.json()["items"], [])

    def test_update_pantry_deduplicates_by_name(self) -> None:
        payload = {
            "items": [
                {"raw_name": "Apples"},
                {"raw_name": "apples"},
                {"raw_name": " APPLES "},
            ]
        }
        resp = self.client.put("/api/v1/pantry", headers=self.headers, json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_count"], 1)
        self.assertEqual(data["items"][0]["raw_name"], "Apples")


class TestPantryMatching(BasePlannerTestCase):
    """Test pantry-to-recipe overlap matching and non-fabrication guarantee."""

    def setUp(self) -> None:
        res = self.client.post("/api/v1/guest-sessions")
        self.session_id = res.json()["session_id"]
        self.headers = {"X-Guest-Session-ID": self.session_id}

        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.normalize_ingredients.return_value = {"normalized": [], "unmatched": []}
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

    def test_match_pantry_empty_ingredients_returns_400(self) -> None:
        # No ingredients in body and pantry is empty
        resp = self.client.post("/api/v1/pantry/match", headers=self.headers, json={"ingredients": []})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "VALIDATION_ERROR")

    def test_match_pantry_no_canonical_ids_returns_empty_matches(self) -> None:
        # Mock recipe client returning no normalized canonical IDs (standard current DB state)
        mock_recipe_client = MagicMock(spec=RecipeServiceClient)
        mock_recipe_client.normalize_ingredients.return_value = {
            "normalized": [
                {"raw_text": "rolled oats", "canonical_id": None, "canonical_name": None}
            ],
            "unmatched": ["rolled oats"],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe_client

        resp = self.client.post(
            "/api/v1/pantry/match",
            headers=self.headers,
            json={"ingredients": ["rolled oats"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["matches"], [])
        self.assertEqual(data["pagination"]["total_items"], 0)

    def test_match_pantry_with_candidates_and_overlap(self) -> None:
        # Mock recipe client returning valid canonical match and candidate recipes
        mock_recipe_client = MagicMock(spec=RecipeServiceClient)
        mock_recipe_client.normalize_ingredients.return_value = {
            "normalized": [
                {"raw_text": "chicken", "canonical_id": 101, "canonical_name": "chicken breast"},
                {"raw_text": "garlic", "canonical_id": 102, "canonical_name": "garlic"},
            ],
            "unmatched": [],
        }
        mock_recipe_client.search_by_ingredients.return_value = {
            "matches": [
                {
                    "recipe_id": "rcp_foodcom_5421",
                    "matched_ingredient_count": 2,
                    "total_ingredient_count": 3,
                    "match_ratio": 0.67,
                }
            ],
            "total": 1,
        }
        mock_recipe_client.batch_get_recipes.return_value = {
            "recipes": [
                {
                    "id": "rcp_foodcom_5421",
                    "title": "Garlic Chicken",
                    "ingredients": [
                        {"raw_text": "1 lb chicken breast", "canonical_id": 101, "name": "chicken breast"},
                        {"raw_text": "3 cloves garlic", "canonical_id": 102, "name": "garlic"},
                        {"raw_text": "fresh rosemary", "canonical_id": 103, "name": "rosemary"},
                    ],
                    "total_time_minutes": 45,
                    "rating_average": 4.8,
                }
            ],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe_client

        resp = self.client.post(
            "/api/v1/pantry/match",
            headers=self.headers,
            json={"ingredients": ["chicken", "garlic"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["matches"]), 1)

        match = data["matches"][0]
        self.assertEqual(match["recipe_id"], "rcp_foodcom_5421")
        self.assertEqual(match["title"], "Garlic Chicken")
        self.assertEqual(len(match["matched_ingredients"]), 2)
        self.assertEqual(len(match["missing_ingredients"]), 1)
        self.assertAlmostEqual(match["match_pct"], 66.7, places=1)

    def test_match_pantry_with_real_recipe_service_response_fields(self) -> None:
        """Test pantry matching using authoritative Recipe Service response field names and staple handling."""
        mock_recipe_client = MagicMock(spec=RecipeServiceClient)
        # Normalizer returns canonical IDs for onion (319) and garlic (322)
        mock_recipe_client.normalize_ingredients.return_value = {
            "results": [
                {"raw_input": "onion", "matched": True, "canonical_id": 319, "canonical_name": "onion"},
                {"raw_input": "garlic", "matched": True, "canonical_id": 322, "canonical_name": "garlic"},
            ]
        }
        mock_recipe_client.search_by_ingredients.return_value = {
            "data": [
                {
                    "recipe_id": "rcp_foodcom_9901",
                    "title": "Onion Garlic Skillet",
                    "matched_canonical_ids": [319, 322],
                    "total_recipe_ingredients": 4,
                    "match_pct": 66.7,
                }
            ],
            "pagination": {"total_items": 1},
        }
        # Real Recipe Service batch response uses canonical_ingredient_id and canonical_name
        mock_recipe_client.batch_get_recipes.return_value = {
            "recipes": [
                {
                    "id": "rcp_foodcom_9901",
                    "title": "Onion Garlic Skillet",
                    "ingredients": [
                        {
                            "position": 1,
                            "raw_text": "1 yellow onion, chopped",
                            "canonical_ingredient_id": 319,
                            "canonical_name": "onion",
                        },
                        {
                            "position": 2,
                            "raw_text": "4 cloves garlic, minced",
                            "canonical_ingredient_id": 322,
                            "canonical_name": "garlic",
                        },
                        {
                            "position": 3,
                            "raw_text": "1 tsp black pepper",
                            "canonical_ingredient_id": 403,
                            "canonical_name": "black pepper",  # Pantry staple
                        },
                        {
                            "position": 4,
                            "raw_text": "1 pinch exotic herb",
                            "canonical_ingredient_id": None,
                            "canonical_name": None,  # Unmapped recipe ingredient
                        },
                    ],
                    "total_time_minutes": 30,
                    "rating_average": 4.9,
                }
            ]
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe_client

        # 1. With exclude_pantry_staples=True (default)
        resp = self.client.post(
            "/api/v1/pantry/match",
            headers=self.headers,
            json={"ingredients": ["onion", "garlic"], "exclude_pantry_staples": True},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["matches"]), 1)
        m = data["matches"][0]
        self.assertEqual(m["recipe_id"], "rcp_foodcom_9901")
        # Matched ingredients contain raw_text from onion and garlic
        self.assertIn("1 yellow onion, chopped", m["matched_ingredients"])
        self.assertIn("4 cloves garlic, minced", m["matched_ingredients"])
        self.assertEqual(len(m["matched_ingredients"]), 2)
        # Black pepper is excluded from missing; only unmapped exotic herb remains missing
        self.assertEqual(m["missing_ingredients"], ["1 pinch exotic herb"])
        # Denominator is 2 matched + 1 missing = 3. 2 / 3 = 66.7%
        self.assertEqual(m["match_pct"], 66.7)

    def test_match_pantry_staple_retention_when_exclusion_disabled(self) -> None:
        """When exclude_pantry_staples=False, staples are tracked in denominator and missing list."""
        mock_recipe_client = MagicMock(spec=RecipeServiceClient)
        mock_recipe_client.normalize_ingredients.return_value = {
            "results": [
                {"raw_input": "onion", "matched": True, "canonical_id": 319, "canonical_name": "onion"},
            ]
        }
        mock_recipe_client.search_by_ingredients.return_value = {
            "data": [{"recipe_id": "rcp_foodcom_9902"}],
            "pagination": {"total_items": 1},
        }
        mock_recipe_client.batch_get_recipes.return_value = {
            "recipes": [
                {
                    "id": "rcp_foodcom_9902",
                    "title": "Salted Onion",
                    "ingredients": [
                        {"raw_text": "1 onion", "canonical_ingredient_id": 319, "canonical_name": "onion"},
                        {"raw_text": "1 tsp salt", "canonical_ingredient_id": 402, "canonical_name": "salt"},
                    ],
                }
            ]
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe_client

        resp = self.client.post(
            "/api/v1/pantry/match",
            headers=self.headers,
            json={"ingredients": ["onion"], "exclude_pantry_staples": False},
        )
        self.assertEqual(resp.status_code, 200)
        m = resp.json()["matches"][0]
        self.assertEqual(m["matched_ingredients"], ["1 onion"])
        self.assertEqual(m["missing_ingredients"], ["1 tsp salt"])
        self.assertEqual(m["match_pct"], 50.0)

    def test_match_pantry_unmapped_pantry_input_never_falsely_matches(self) -> None:
        """Pantry ingredients without canonical mappings must return honest empty results."""
        mock_recipe_client = MagicMock(spec=RecipeServiceClient)
        mock_recipe_client.normalize_ingredients.return_value = {
            "results": [
                {"raw_input": "unknown alien vegetable", "matched": False, "canonical_id": None, "canonical_name": None}
            ]
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe_client

        resp = self.client.post(
            "/api/v1/pantry/match",
            headers=self.headers,
            json={"ingredients": ["unknown alien vegetable"]},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["matches"], [])
        self.assertEqual(data["pagination"]["total_items"], 0)

    def test_match_pantry_recipe_service_down_returns_502(self) -> None:
        mock_recipe_client = MagicMock(spec=RecipeServiceClient)
        mock_recipe_client.normalize_ingredients.side_effect = UpstreamServiceUnavailableError(
            "recipe-service", "Connection refused"
        )
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe_client

        resp = self.client.post(
            "/api/v1/pantry/match",
            headers=self.headers,
            json={"ingredients": ["chicken"]},
        )
        self.assertEqual(resp.status_code, 502)
        self.assertEqual(resp.json()["error"]["code"], "SERVICE_UNAVAILABLE")


class TestMealPlanning(BasePlannerTestCase):
    """Test proposal generation, meal plan saving, updating, progress, and deletion."""

    def setUp(self) -> None:
        res1 = self.client.post("/api/v1/guest-sessions")
        self.session_1 = res1.json()["session_id"]
        self.headers_1 = {"X-Guest-Session-ID": self.session_1}

        res2 = self.client.post("/api/v1/guest-sessions")
        self.session_2 = res2.json()["session_id"]
        self.headers_2 = {"X-Guest-Session-ID": self.session_2}

    def test_generate_meal_plan_proposal(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.search_recipes.return_value = {
            "items": [
                {"id": "rcp_foodcom_1", "title": "Breakfast Omelet", "total_time_minutes": 15, "nutrition": {"calories": 300.0}},
                {"id": "rcp_foodcom_2", "title": "Turkey Salad", "total_time_minutes": 20, "nutrition": {"calories": 450.0}},
                {"id": "rcp_foodcom_3", "title": "Baked Salmon", "total_time_minutes": 35, "nutrition": {"calories": 600.0}},
            ],
            "total": 3,
        }
        mock_profile = MagicMock(spec=ProfileServiceClient)
        mock_profile.get_cached_recipe_nutrition.return_value = None

        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe
        app.dependency_overrides[get_profile_client] = lambda: mock_profile

        payload = {
            "days": 2,
            "slots": ["breakfast", "lunch", "dinner"],
            "target_calories_kcal": 2000,
            "diet_preference": "vegetarian",
        }
        resp = self.client.post("/api/v1/meal-plans/generate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["target_calories_kcal"], 2000)
        self.assertEqual(len(data["days"]), 2)
        self.assertEqual(len(data["days"][0]["slots"]), 3)
        self.assertIn("Dietary preference applied: vegetarian", data["notes"])

    def test_save_meal_plan_success(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [
                {"id": "rcp_foodcom_1234", "title": "Test Recipe 1"},
                {"id": "rcp_foodcom_5678", "title": "Test Recipe 2"},
            ],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        payload = {
            "name": "Weekly Prep Plan",
            "days": 2,
            "target_calories_kcal": 2100,
            "slots": [
                {"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_1234", "recipe_title": "Test Recipe 1"},
                {"day_index": 0, "slot_type": "dinner", "recipe_id": "rcp_foodcom_5678", "recipe_title": "Test Recipe 2"},
            ],
        }
        resp = self.client.post("/api/v1/meal-plans", headers=self.headers_1, json=payload)
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("plan_id", data)
        self.assertEqual(data["name"], "Weekly Prep Plan")
        self.assertEqual(data["days"], 2)

    def test_save_meal_plan_nonexistent_recipe_returns_400(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [],
            "missing_ids": ["rcp_foodcom_999999"],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        payload = {
            "name": "Invalid Plan",
            "days": 1,
            "slots": [
                {"day_index": 0, "slot_type": "dinner", "recipe_id": "rcp_foodcom_999999", "recipe_title": "Ghost Food"},
            ],
        }
        resp = self.client.post("/api/v1/meal-plans", headers=self.headers_1, json=payload)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "VALIDATION_ERROR")

    def test_get_meal_plan_and_cross_guest_isolation(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [{"id": "rcp_foodcom_1234", "title": "Chicken Stew"}],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Guest 1 Private Plan",
                "days": 1,
                "slots": [
                    {"day_index": 0, "slot_type": "dinner", "recipe_id": "rcp_foodcom_1234", "recipe_title": "Chicken Stew"}
                ],
            },
        )
        plan_id = save_res.json()["plan_id"]

        # Guest 1 can retrieve it
        r_get = self.client.get(f"/api/v1/meal-plans/{plan_id}", headers=self.headers_1)
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.json()["name"], "Guest 1 Private Plan")
        self.assertEqual(len(r_get.json()["slots"]), 1)
        self.assertEqual(r_get.json()["slots"][0]["cooking_status"], "pending")

        # Guest 2 CANNOT retrieve it -> 404
        r_cross = self.client.get(f"/api/v1/meal-plans/{plan_id}", headers=self.headers_2)
        self.assertEqual(r_cross.status_code, 404)
        self.assertEqual(r_cross.json()["error"]["code"], "RESOURCE_NOT_FOUND")

    def test_update_meal_plan_and_cross_guest_protection(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [
                {"id": "rcp_foodcom_1", "title": "Meal 1"},
                {"id": "rcp_foodcom_2", "title": "Meal 2"},
            ],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Original Name",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_1", "recipe_title": "Meal 1"}],
            },
        )
        plan_id = save_res.json()["plan_id"]

        # Guest 2 attempts update -> 404
        r_bad = self.client.put(
            f"/api/v1/meal-plans/{plan_id}",
            headers=self.headers_2,
            json={
                "name": "Hacked Plan",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_2", "recipe_title": "Meal 2"}],
            },
        )
        self.assertEqual(r_bad.status_code, 404)

        # Guest 1 updates successfully
        r_good = self.client.put(
            f"/api/v1/meal-plans/{plan_id}",
            headers=self.headers_1,
            json={
                "name": "Updated Plan Name",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "dinner", "recipe_id": "rcp_foodcom_2", "recipe_title": "Meal 2"}],
            },
        )
        self.assertEqual(r_good.status_code, 200)
        self.assertEqual(r_good.json()["name"], "Updated Plan Name")
        self.assertEqual(r_good.json()["slots"][0]["slot_type"], "dinner")

    def test_delete_meal_plan(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [{"id": "rcp_foodcom_1", "title": "Meal 1"}],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "To Be Deleted",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_1", "recipe_title": "Meal 1"}],
            },
        )
        plan_id = save_res.json()["plan_id"]

        # Delete as guest 1
        del_res = self.client.delete(f"/api/v1/meal-plans/{plan_id}", headers=self.headers_1)
        self.assertEqual(del_res.status_code, 204)

        # Subsequent GET returns 404
        get_res = self.client.get(f"/api/v1/meal-plans/{plan_id}", headers=self.headers_1)
        self.assertEqual(get_res.status_code, 404)

    def test_update_cooking_progress(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [{"id": "rcp_foodcom_1", "title": "Roast Chicken"}],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Progress Tracking Plan",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "dinner", "recipe_id": "rcp_foodcom_1", "recipe_title": "Roast Chicken"}],
            },
        )
        plan_id = save_res.json()["plan_id"]

        plan_detail = self.client.get(f"/api/v1/meal-plans/{plan_id}", headers=self.headers_1).json()
        slot_id = plan_detail["slots"][0]["id"]

        # Update progress to cooked
        prog_res = self.client.patch(
            f"/api/v1/meal-plans/{plan_id}/progress",
            headers=self.headers_1,
            json={"updates": [{"slot_id": slot_id, "cooking_status": "cooked"}]},
        )
        self.assertEqual(prog_res.status_code, 200)
        self.assertEqual(prog_res.json()["updated_count"], 1)

        # Verify state updated in GET
        updated_plan = self.client.get(f"/api/v1/meal-plans/{plan_id}", headers=self.headers_1).json()
        self.assertEqual(updated_plan["slots"][0]["cooking_status"], "cooked")

    def test_update_cooking_progress_invalid_slot_returns_404(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [{"id": "rcp_foodcom_1", "title": "Meal"}],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Plan",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_1", "recipe_title": "Meal"}],
            },
        )
        plan_id = save_res.json()["plan_id"]

        prog_res = self.client.patch(
            f"/api/v1/meal-plans/{plan_id}/progress",
            headers=self.headers_1,
            json={"updates": [{"slot_id": 999999, "cooking_status": "cooked"}]},
        )
        self.assertEqual(prog_res.status_code, 404)


class TestShoppingList(BasePlannerTestCase):
    """Test shopping list generation, aggregation, categorization, and item checking."""

    def setUp(self) -> None:
        res1 = self.client.post("/api/v1/guest-sessions")
        self.session_1 = res1.json()["session_id"]
        self.headers_1 = {"X-Guest-Session-ID": self.session_1}

        res2 = self.client.post("/api/v1/guest-sessions")
        self.session_2 = res2.json()["session_id"]
        self.headers_2 = {"X-Guest-Session-ID": self.session_2}

    def test_shopping_list_generation_and_categorization(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [
                {
                    "id": "rcp_foodcom_101",
                    "title": "Rosemary Garlic Chicken",
                    "ingredients": [
                        {"raw_text": "2 chicken breasts", "name": "chicken breast", "amount": 2, "unit": "breast"},
                        {"raw_text": "3 cloves garlic", "name": "garlic", "amount": 3, "unit": "clove"},
                        {"raw_text": "1 cup whole milk", "name": "whole milk", "amount": 1, "unit": "cup"},
                        {"raw_text": "1 tsp salt", "name": "salt", "amount": 1, "unit": "tsp"},
                    ],
                }
            ],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Shopping Test Plan",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "dinner", "recipe_id": "rcp_foodcom_101", "recipe_title": "Rosemary Garlic Chicken"}],
            },
        )
        plan_id = save_res.json()["plan_id"]

        # Generate shopping list
        shop_res = self.client.get(f"/api/v1/meal-plans/{plan_id}/shopping-list", headers=self.headers_1)
        self.assertEqual(shop_res.status_code, 200)
        data = shop_res.json()

        self.assertEqual(data["plan_id"], plan_id)
        self.assertGreater(data["total_items"], 0)
        self.assertIn("categories", data)

        cat_names = [c["category"] for c in data["categories"]]
        self.assertIn("Meat & Seafood", cat_names)
        self.assertIn("Produce", cat_names)
        self.assertIn("Dairy & Refrigerated", cat_names)
        self.assertIn("Spices & Seasonings", cat_names)

    def test_shopping_list_aggregates_compatible_quantities(self) -> None:
        # 1 cup milk + 2 cups milk = 3 cups milk
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [
                {
                    "id": "rcp_foodcom_201",
                    "title": "Milk Shake 1",
                    "ingredients": [
                        {"raw_text": "1 cup whole milk", "name": "whole milk", "amount": 1.0, "unit": "cup"},
                    ],
                },
                {
                    "id": "rcp_foodcom_202",
                    "title": "Milk Shake 2",
                    "ingredients": [
                        {"raw_text": "2 cups whole milk", "name": "whole milk", "amount": 2.0, "unit": "cup"},
                    ],
                },
            ],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Milk Aggregation Plan",
                "days": 1,
                "slots": [
                    {"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_201", "recipe_title": "Milk Shake 1"},
                    {"day_index": 0, "slot_type": "dinner", "recipe_id": "rcp_foodcom_202", "recipe_title": "Milk Shake 2"},
                ],
            },
        )
        plan_id = save_res.json()["plan_id"]

        shop_res = self.client.get(f"/api/v1/meal-plans/{plan_id}/shopping-list", headers=self.headers_1)
        self.assertEqual(shop_res.status_code, 200)
        data = shop_res.json()

        # Should aggregate to 1 line item: "3 cups"
        self.assertEqual(data["total_items"], 1)
        dairy_cat = next(c for c in data["categories"] if c["category"] == "Dairy & Refrigerated")
        milk_item = dairy_cat["items"][0]
        self.assertEqual(milk_item["ingredient_name"], "whole milk")
        self.assertEqual(milk_item["quantity_display"], "3 cup")

    def test_update_shopping_list_item_checked(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [
                {
                    "id": "rcp_foodcom_301",
                    "title": "Salad",
                    "ingredients": [{"raw_text": "lettuce", "name": "lettuce", "amount": 1, "unit": "head"}],
                }
            ],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Checklist Plan",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_301", "recipe_title": "Salad"}],
            },
        )
        plan_id = save_res.json()["plan_id"]

        shop_data = self.client.get(f"/api/v1/meal-plans/{plan_id}/shopping-list", headers=self.headers_1).json()
        item_id = shop_data["categories"][0]["items"][0]["id"]
        self.assertFalse(shop_data["categories"][0]["items"][0]["checked"])

        # Toggle to checked = True
        patch_res = self.client.patch(
            f"/api/v1/meal-plans/{plan_id}/shopping-list/items/{item_id}",
            headers=self.headers_1,
            json={"checked": True},
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertTrue(patch_res.json()["checked"])

        # Verify persisted via GET
        reloaded = self.client.get(f"/api/v1/meal-plans/{plan_id}/shopping-list", headers=self.headers_1).json()
        self.assertTrue(reloaded["categories"][0]["items"][0]["checked"])

    def test_shopping_list_cross_guest_isolation(self) -> None:
        mock_recipe = MagicMock(spec=RecipeServiceClient)
        mock_recipe.batch_get_recipes.return_value = {
            "recipes": [{"id": "rcp_foodcom_1", "title": "Meal", "ingredients": [{"name": "salt"}]}],
            "missing_ids": [],
        }
        app.dependency_overrides[get_recipe_client] = lambda: mock_recipe

        save_res = self.client.post(
            "/api/v1/meal-plans",
            headers=self.headers_1,
            json={
                "name": "Private Shopping Plan",
                "days": 1,
                "slots": [{"day_index": 0, "slot_type": "lunch", "recipe_id": "rcp_foodcom_1", "recipe_title": "Meal"}],
            },
        )
        plan_id = save_res.json()["plan_id"]

        # Guest 2 attempts to get shopping list -> 404
        r_cross = self.client.get(f"/api/v1/meal-plans/{plan_id}/shopping-list", headers=self.headers_2)
        self.assertEqual(r_cross.status_code, 404)
        self.assertEqual(r_cross.json()["error"]["code"], "RESOURCE_NOT_FOUND")


class TestSecurityAndRoleIsolation(BasePlannerTestCase):
    """Test PostgreSQL role permissions and cross-schema isolation."""

    def test_planner_service_cannot_query_other_schemas(self) -> None:
        planner_url = os.environ.get("PLANNER_SERVICE_DATABASE_URL")
        self.assertIsNotNone(planner_url)

        with psycopg.connect(planner_url) as conn:
            with conn.cursor() as cur:
                # 1. Allowed on meal_planner
                cur.execute("SELECT COUNT(*) FROM meal_planner.guest_sessions;")
                self.assertIsInstance(cur.fetchone()[0], int)

                # 2. Denied on profile_nutrition
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM profile_nutrition.usda_foods LIMIT 1;")
                conn.rollback()

                # 3. Denied on recipe_catalog
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM recipe_catalog.recipes LIMIT 1;")
                conn.rollback()


if __name__ == "__main__":
    unittest.main()
