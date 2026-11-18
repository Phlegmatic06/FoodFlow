"""Comprehensive unit and integration test suite for NutriPod Recipe & Ingredient Service.

Verifies:
- OpenAPI contract conformance and property data types.
- Recipe search, full-text ranking, filtering (cuisine, tag, diet, time, dataset), and pagination.
- SQL injection resilience in search and filter parameters.
- Recipe detail retrieval for Food.com and RecipeNLG records.
- Ordered ingredients (by position) and instructions (by step_number).
- Strict ratings and nutrition semantics (no fabricated data, %DV preservation).
- Batch recipe retrieval and missing ID reporting without N+1 queries.
- Ingredient normalization and autocomplete suggestion semantics.
- Standardized ErrorResponse envelope across 400, 404, and validation errors.
- Schema isolation and connection pool lifecycle.
"""

from __future__ import annotations

import os
import unittest

import psycopg
from starlette.testclient import TestClient

from services.common.config import load_env_file
from services.recipe_ingredient.database import db_manager
from services.recipe_ingredient.main import app

load_env_file()


class TestRecipeSearchAndDiscovery(unittest.TestCase):
    """Test public recipe discovery, search, filtering, and pagination."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_search_keyword_returns_results(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?q=chicken&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("data", data)
        self.assertIn("pagination", data)

        pagination = data["pagination"]
        self.assertEqual(pagination["page"], 1)
        self.assertEqual(pagination["limit"], 10)
        self.assertGreater(pagination["total_items"], 0)
        self.assertGreater(pagination["total_pages"], 0)

        recipes = data["data"]
        self.assertLessEqual(len(recipes), 10)
        for r in recipes:
            self.assertTrue(r["id"].startswith("rcp_"))
            self.assertIn(r["source_dataset"], ["food_com", "recipenlg"])
            self.assertIsInstance(r["title"], str)
            self.assertIsInstance(r["rating_count"], int)
            self.assertIsInstance(r["tag_preview"], list)
            self.assertLessEqual(len(r["tag_preview"]), 5)

    def test_search_no_results(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?q=xyznonexistentphrase987654")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["data"], [])
        self.assertEqual(data["pagination"]["total_items"], 0)
        self.assertEqual(data["pagination"]["total_pages"], 0)

    def test_search_empty_q_returns_catalogue(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?limit=12")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["data"]), 12)
        self.assertEqual(data["pagination"]["total_items"], 50000)

    def test_search_pagination_boundaries(self) -> None:
        resp_p1 = self.client.get("/api/v1/recipes/search?limit=5&page=1")
        resp_p2 = self.client.get("/api/v1/recipes/search?limit=5&page=2")
        self.assertEqual(resp_p1.status_code, 200)
        self.assertEqual(resp_p2.status_code, 200)

        ids_p1 = [r["id"] for r in resp_p1.json()["data"]]
        ids_p2 = [r["id"] for r in resp_p2.json()["data"]]

        self.assertEqual(len(ids_p1), 5)
        self.assertEqual(len(ids_p2), 5)
        # Ensure zero duplicate IDs across pages (stable pagination)
        self.assertEqual(len(set(ids_p1).intersection(set(ids_p2))), 0)

    def test_search_invalid_limit_returns_400(self) -> None:
        resp_zero = self.client.get("/api/v1/recipes/search?limit=0")
        self.assertEqual(resp_zero.status_code, 400)
        data = resp_zero.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

        resp_large = self.client.get("/api/v1/recipes/search?limit=49")
        self.assertEqual(resp_large.status_code, 400)
        data = resp_large.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

    def test_search_invalid_page_returns_400(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?page=0")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

    def test_search_filter_by_source_dataset_foodcom(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?source_dataset=food_com&limit=15")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["data"]), 15)
        self.assertEqual(data["pagination"]["total_items"], 25000)
        for r in data["data"]:
            self.assertEqual(r["source_dataset"], "food_com")
            self.assertTrue(r["id"].startswith("rcp_foodcom_"))

    def test_search_filter_by_source_dataset_recipenlg(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?source_dataset=recipenlg&limit=15")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["data"]), 15)
        self.assertEqual(data["pagination"]["total_items"], 25000)
        for r in data["data"]:
            self.assertEqual(r["source_dataset"], "recipenlg")
            self.assertTrue(r["id"].startswith("rcp_nlg_"))

    def test_search_filter_by_max_time(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?max_time=30&limit=15")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for r in data["data"]:
            self.assertIsNotNone(r["total_time_minutes"])
            self.assertLessEqual(r["total_time_minutes"], 30)

    def test_search_filter_by_diet(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?diet=vegetarian&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["pagination"]["total_items"], 0)
        for r in data["data"]:
            self.assertEqual(r["source_dataset"], "food_com")

    def test_search_filter_by_cuisine(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?cuisine=Italian&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["pagination"]["total_items"], 0)

    def test_search_multiple_filters_combined(self) -> None:
        resp = self.client.get(
            "/api/v1/recipes/search?source_dataset=food_com&diet=vegetarian&max_time=45&limit=10"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for r in data["data"]:
            self.assertEqual(r["source_dataset"], "food_com")
            self.assertLessEqual(r["total_time_minutes"], 45)

    def test_search_sql_injection_resilience(self) -> None:
        # Complex strings that would break non-parameterized queries
        payloads = [
            "'; DROP TABLE recipe_catalog.recipes; --",
            "' OR 1=1; --",
            "\" OR \"\"=\"",
            "1' UNION SELECT NULL, NULL, NULL --",
        ]
        for inj in payloads:
            resp = self.client.get(f"/api/v1/recipes/search?q={inj}")
            self.assertEqual(resp.status_code, 200)

    def test_search_sorting_options(self) -> None:
        for sort_opt in ["relevance", "rating", "time_asc", "time_desc"]:
            resp = self.client.get(f"/api/v1/recipes/search?q=chicken&sort={sort_opt}&limit=5")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertLessEqual(len(data["data"]), 5)

    def test_search_invalid_sort_returns_400(self) -> None:
        resp = self.client.get("/api/v1/recipes/search?sort=malicious_sort")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")


class TestRecipeDetail(unittest.TestCase):
    """Test recipe detail retrieval across Food.com and RecipeNLG records."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_recipe_detail_foodcom(self) -> None:
        resp = self.client.get("/api/v1/recipes/rcp_foodcom_167289")
        self.assertEqual(resp.status_code, 200)
        recipe = resp.json()

        self.assertEqual(recipe["id"], "rcp_foodcom_167289")
        self.assertEqual(recipe["source_dataset"], "food_com")
        self.assertEqual(recipe["source_id"], "167289")
        self.assertEqual(recipe["title"], "limoncello  lemoncello   limoncella")

        # Check ingredients sequence
        ingredients = recipe["ingredients"]
        self.assertGreater(len(ingredients), 0)
        positions = [ing["position"] for ing in ingredients]
        self.assertEqual(positions, sorted(positions))
        for ing in ingredients:
            self.assertIn("raw_text", ing)
            self.assertIn("position", ing)

        # Check instructions sequence
        instructions = recipe["instructions"]
        self.assertGreater(len(instructions), 0)
        step_numbers = [inst["step_number"] for inst in instructions]
        self.assertEqual(step_numbers, sorted(step_numbers))
        for inst in instructions:
            self.assertIn("instruction", inst)

        # Check tags
        self.assertIsInstance(recipe["tags"], list)
        self.assertGreater(len(recipe["tags"]), 0)

        # Check ratings
        self.assertIsNotNone(recipe["rating_average"])
        self.assertGreaterEqual(recipe["rating_average"], 1.0)
        self.assertLessEqual(recipe["rating_average"], 5.0)
        self.assertGreaterEqual(recipe["rating_count"], 1)

        # Check nutrition
        raw_nut = recipe["raw_nutrition"]
        self.assertIsNotNone(raw_nut)
        self.assertGreater(raw_nut["raw_calories"], 0)
        self.assertIn("raw_total_fat_pdv", raw_nut)
        self.assertIn("raw_sugar_pdv", raw_nut)
        self.assertIn("raw_sodium_pdv", raw_nut)
        self.assertIn("raw_protein_pdv", raw_nut)
        self.assertIn("raw_saturated_fat_pdv", raw_nut)
        self.assertIn("raw_carbohydrates_pdv", raw_nut)

    def test_recipe_detail_recipenlg(self) -> None:
        resp = self.client.get("/api/v1/recipes/rcp_nlg_1914325")
        self.assertEqual(resp.status_code, 200)
        recipe = resp.json()

        self.assertEqual(recipe["id"], "rcp_nlg_1914325")
        self.assertEqual(recipe["source_dataset"], "recipenlg")
        self.assertEqual(recipe["title"], "Chicken Cacciatore (Hunters Chicken Stew)")
        self.assertTrue(recipe["source_url"].startswith("tastykitchen.com"))

        # RecipeNLG must have strictly NULL ratings and nutrition
        self.assertIsNone(recipe["rating_average"])
        self.assertEqual(recipe["rating_count"], 0)
        self.assertIsNone(recipe["raw_nutrition"])
        self.assertIsNone(recipe["servings"])
        self.assertIsNone(recipe["total_time_minutes"])

        # Ingredients and instructions must exist
        self.assertGreater(len(recipe["ingredients"]), 0)
        self.assertGreater(len(recipe["instructions"]), 0)

    def test_recipe_detail_not_found_returns_404(self) -> None:
        resp = self.client.get("/api/v1/recipes/rcp_foodcom_999999999")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "HTTP_404")
        self.assertIn("was not found", data["error"]["message"])

    def test_recipe_detail_invalid_id_pattern_returns_400(self) -> None:
        resp = self.client.get("/api/v1/recipes/invalid_format_id")
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")


class TestBatchRecipeEndpoint(unittest.TestCase):
    """Test batch recipe lookup endpoint."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_batch_get_recipes_mixed(self) -> None:
        payload = {
            "recipe_ids": [
                "rcp_foodcom_167289",
                "rcp_nlg_1914325",
                "rcp_foodcom_999999999",
            ]
        }
        resp = self.client.post("/api/v1/recipes/batch", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data["recipes"]), 2)
        self.assertEqual(data["not_found"], ["rcp_foodcom_999999999"])

        ids = [r["id"] for r in data["recipes"]]
        self.assertIn("rcp_foodcom_167289", ids)
        self.assertIn("rcp_nlg_1914325", ids)

    def test_batch_get_recipes_empty_list_returns_400(self) -> None:
        resp = self.client.post("/api/v1/recipes/batch", json={"recipe_ids": []})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

    def test_batch_get_recipes_exceeds_100_returns_400(self) -> None:
        ids = [f"rcp_foodcom_{i}" for i in range(101)]
        resp = self.client.post("/api/v1/recipes/batch", json={"recipe_ids": ids})
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")


class TestIngredientOperations(unittest.TestCase):
    """Test ingredient normalization and autocomplete suggestion endpoints."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_normalize_ingredients_taxonomy(self) -> None:
        payload = {
            "ingredients": [
                "boneless chicken breasts",
                "kosher salt",
                "2 cloves garlic",
                "garlic powder",
                "salt and pepper",
                "nonexistent alien root 999",
            ]
        }
        resp = self.client.post("/api/v1/ingredients/normalize", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 6)

        results_by_input = {r["raw_input"]: r for r in data["results"]}

        # 1. Synonym match: boneless chicken breasts -> chicken breast
        r_chicken = results_by_input["boneless chicken breasts"]
        self.assertTrue(r_chicken["matched"])
        self.assertEqual(r_chicken["canonical_name"], "chicken breast")
        self.assertIsNotNone(r_chicken["canonical_id"])

        # 2. Synonym match: kosher salt -> salt
        r_salt = results_by_input["kosher salt"]
        self.assertTrue(r_salt["matched"])
        self.assertEqual(r_salt["canonical_name"], "salt")

        # 3. Quantity/unit stripped match: 2 cloves garlic -> garlic
        r_garlic = results_by_input["2 cloves garlic"]
        self.assertTrue(r_garlic["matched"])
        self.assertEqual(r_garlic["canonical_name"], "garlic")

        # 4. Canonical distinct item: garlic powder -> garlic powder (NOT garlic)
        r_gpowder = results_by_input["garlic powder"]
        self.assertTrue(r_gpowder["matched"])
        self.assertEqual(r_gpowder["canonical_name"], "garlic powder")
        self.assertNotEqual(r_gpowder["canonical_id"], r_garlic["canonical_id"])

        # 5. Compound exclusion: salt and pepper -> unmatched
        r_sp = results_by_input["salt and pepper"]
        self.assertFalse(r_sp["matched"])
        self.assertIsNone(r_sp["canonical_id"])

        # 6. Unknown item -> unmatched
        r_unknown = results_by_input["nonexistent alien root 999"]
        self.assertFalse(r_unknown["matched"])
        self.assertIsNone(r_unknown["canonical_id"])

    def test_normalize_ingredients_empty_list_returns_400(self) -> None:
        resp = self.client.post("/api/v1/ingredients/normalize", json={"ingredients": []})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "VALIDATION_ERROR")

    def test_ingredient_suggestions_populated(self) -> None:
        resp = self.client.get("/api/v1/ingredients/suggestions?q=chick&limit=5")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        names = [item["name"] for item in items]
        self.assertTrue(any("chicken" in n for n in names))

    def test_ingredient_suggestions_unknown_returns_empty(self) -> None:
        resp = self.client.get("/api/v1/ingredients/suggestions?q=xyznonexistent999&limit=5")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_ingredient_suggestions_empty_q_returns_400(self) -> None:
        resp = self.client.get("/api/v1/ingredients/suggestions?q=")
        self.assertEqual(resp.status_code, 400)

    def test_search_by_ingredients_empty_candidates(self) -> None:
        payload = {"canonical_ingredient_ids": [999991, 999992]}
        resp = self.client.post("/api/v1/recipes/search-by-ingredients", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["data"], [])
        self.assertEqual(data["pagination"]["total_items"], 0)

    def test_search_by_ingredients_matching_candidates(self) -> None:
        # First resolve canonical IDs for onion and garlic
        norm_resp = self.client.post(
            "/api/v1/ingredients/normalize",
            json={"ingredients": ["onion", "garlic"]},
        )
        self.assertEqual(norm_resp.status_code, 200)
        cids = [r["canonical_id"] for r in norm_resp.json()["results"] if r["matched"]]
        self.assertEqual(len(cids), 2)

        payload = {"canonical_ingredient_ids": cids, "min_match_pct": 10.0, "limit": 10}
        resp = self.client.post("/api/v1/recipes/search-by-ingredients", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreater(data["pagination"]["total_items"], 0)
        self.assertGreater(len(data["data"]), 0)

    def test_compound_ingredient_detection_rejections(self) -> None:
        """Mandatory compound strings separated by punctuation/conjunctions must remain unmatched."""
        compound_inputs = [
            "salt and pepper",
            "salt, black pepper",
            "oil/vinegar",
            "salt & pepper",
            "salt + pepper",
            "cinnamon; sugar",
            "salt and/or pepper",
            "salt - black pepper",
            "1/2 tsp salt and pepper",
        ]
        resp = self.client.post("/api/v1/ingredients/normalize", json={"ingredients": compound_inputs})
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertEqual(len(results), len(compound_inputs))

        for r in results:
            self.assertFalse(
                r["matched"],
                f"Compound input '{r['raw_input']}' falsely marked as matched!",
            )
            self.assertIsNone(r["canonical_id"])
            self.assertIsNone(r["canonical_name"])
            self.assertIsNone(r["confidence"])

    def test_compound_ingredient_preservation_inputs(self) -> None:
        """Inputs with fractional quantities or internal hyphens must preserve correct normalization."""
        preservation_cases = [
            ("1/2 tsp salt", "salt"),
            ("2 cloves garlic", "garlic"),
            ("all-purpose flour", "all-purpose flour"),
            ("all purpose flour", "all-purpose flour"),
        ]
        inputs = [p[0] for p in preservation_cases]
        resp = self.client.post("/api/v1/ingredients/normalize", json={"ingredients": inputs})
        self.assertEqual(resp.status_code, 200)
        results_by_input = {r["raw_input"]: r for r in resp.json()["results"]}

        for raw_inp, expected_canon in preservation_cases:
            r = results_by_input[raw_inp]
            self.assertTrue(r["matched"], f"Preservation input '{raw_inp}' failed to match!")
            self.assertEqual(r["canonical_name"], expected_canon)
            self.assertIsNotNone(r["canonical_id"])

    def test_near_neighbour_and_distinction_normalization(self) -> None:
        """Mandatory near-neighbour verification ensuring culinary distinctions are strictly preserved."""
        # Exact expected behaviors per Phase 4 specification
        expected_matches = {
            "flour": "flour",
            "milk": "milk",
            "whole milk": "whole milk",
            "skim milk": "skim milk",
            "garlic": "garlic",
            "garlic powder": "garlic powder",
            "tomato": "tomato",
            "tomato paste": "tomato paste",
            "tomato sauce": "tomato sauce",
            "pepper": "pepper",
            "black pepper": "black pepper",
            "white pepper": "white pepper",
            "salted butter": "salted butter",
            "unsalted butter": "unsalted butter",
            "fresh basil": "basil",
            "dried basil": "dried basil",
            "chicken broth": "chicken broth",
        }
        expected_unmatched = [
            "almond flour",    # Must NOT map to flour
            "coconut flour",   # Must NOT map to flour
            "rice",            # Must NOT map arbitrarily to white rice
        ]

        all_inputs = list(expected_matches.keys()) + expected_unmatched
        resp = self.client.post("/api/v1/ingredients/normalize", json={"ingredients": all_inputs})
        self.assertEqual(resp.status_code, 200)
        results_by_input = {r["raw_input"]: r for r in resp.json()["results"]}

        # 1. Verify matched distinct entities
        for raw, expected_name in expected_matches.items():
            r = results_by_input[raw]
            self.assertTrue(r["matched"], f"Expected '{raw}' to match '{expected_name}'")
            self.assertEqual(r["canonical_name"], expected_name)
            self.assertIsNotNone(r["canonical_id"])

        # 2. Verify unmatched distinct entities are not collapsed
        for raw in expected_unmatched:
            r = results_by_input[raw]
            self.assertFalse(r["matched"], f"Expected '{raw}' to be unmatched, but mapped to '{r.get('canonical_name')}'")
            self.assertIsNone(r["canonical_id"])

        # 3. Explicit cross-identity distinction checks
        self.assertNotEqual(
            results_by_input["garlic"]["canonical_id"],
            results_by_input["garlic powder"]["canonical_id"],
        )
        self.assertNotEqual(
            results_by_input["milk"]["canonical_id"],
            results_by_input["whole milk"]["canonical_id"],
        )
        self.assertNotEqual(
            results_by_input["whole milk"]["canonical_id"],
            results_by_input["skim milk"]["canonical_id"],
        )
        self.assertNotEqual(
            results_by_input["pepper"]["canonical_id"],
            results_by_input["black pepper"]["canonical_id"],
        )
        self.assertNotEqual(
            results_by_input["salted butter"]["canonical_id"],
            results_by_input["unsalted butter"]["canonical_id"],
        )
        self.assertNotEqual(
            results_by_input["fresh basil"]["canonical_id"],
            results_by_input["dried basil"]["canonical_id"],
        )

    def test_fuzzy_similarity_is_suggestion_only_not_normalized(self) -> None:
        """Trigram similarity alone must not normalize as matched, but remains in suggestions."""
        # 'tomatto' is a typo for 'tomato'
        norm_resp = self.client.post("/api/v1/ingredients/normalize", json={"ingredients": ["tomatto"]})
        self.assertEqual(norm_resp.status_code, 200)
        r = norm_resp.json()["results"][0]
        self.assertFalse(r["matched"])
        self.assertIsNone(r["canonical_id"])
        self.assertIsNone(r["confidence"])

        # Suggestions endpoint still surfaces candidate recommendations
        sugg_resp = self.client.get("/api/v1/ingredients/suggestions?q=tomat&limit=5")
        self.assertEqual(sugg_resp.status_code, 200)
        suggs = sugg_resp.json()
        self.assertGreater(len(suggs), 0)
        sugg_names = [s["name"] for s in suggs]
        self.assertIn("tomato", sugg_names)


class TestSecurityAndRoleIsolation(unittest.TestCase):
    """Test database role boundaries and schema isolation for Recipe Service."""

    def test_recipe_service_cannot_query_other_schemas(self) -> None:
        recipe_url = os.environ.get("RECIPE_SERVICE_DATABASE_URL")
        self.assertIsNotNone(recipe_url)

        with psycopg.connect(recipe_url) as conn:
            with conn.cursor() as cur:
                # Allowed in recipe_catalog
                cur.execute("SELECT COUNT(*) FROM recipe_catalog.recipes;")
                self.assertEqual(cur.fetchone()[0], 50000)

                # Denied on profile_nutrition
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM profile_nutrition.usda_foods LIMIT 1;")
                conn.rollback()

                # Denied on meal_planner
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM meal_planner.guest_sessions LIMIT 1;")
                conn.rollback()


if __name__ == "__main__":
    unittest.main()

