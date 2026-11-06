"""Comprehensive unit and integration test suite for FoodFlow Profile & Nutrition Service.

Verifies:
- OpenAPI contract conformance and property data types.
- Stateless physical biometrics calculation (BMI, BMR via Mifflin-St Jeor, TDEE, macro distribution).
- Graceful handling of omitted biological sex (returns BMI only, zero fabricated metabolic values).
- Goal adjustments and minimum safe calorie floor (1200 kcal).
- Boundary and validation errors for physical measurements.
- USDA FoodData Central search, pagination, and detail queries against live PostgreSQL 16.
- Nutrient measurement and household portion extraction.
- Recipe nutrition estimation (calculated, partial, uncalculated status categories).
- Cached recipe nutrition retrieval and 404 behavior.
- Database role enforcement and strict schema isolation.
"""

from __future__ import annotations

import os
import unittest

import psycopg
from starlette.testclient import TestClient

from services.common.config import load_env_file
from services.profile_nutrition.calculator import (
    calculate_biometrics,
    calculate_bmi,
    calculate_bmr,
)
from services.profile_nutrition.database import db_manager
from services.profile_nutrition.main import app
from services.profile_nutrition.schemas import (
    BiometricsCalculationRequest,
    RecipeIngredientInput,
    RecipeNutritionEstimateRequest,
)

load_env_file()


class TestBiometricsCalculations(unittest.TestCase):
    """Test stateless BMI, BMR, TDEE, and macro distribution calculation logic."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_bmi_calculation_and_categories(self) -> None:
        # Underweight: BMI < 18.5
        bmi_u, cat_u = calculate_bmi(weight_kg=50.0, height_cm=175.0)
        self.assertEqual(bmi_u, 16.33)
        self.assertEqual(cat_u, "underweight")

        # Normal weight: 18.5 <= BMI < 25.0
        bmi_n, cat_n = calculate_bmi(weight_kg=70.0, height_cm=175.0)
        self.assertEqual(bmi_n, 22.86)
        self.assertEqual(cat_n, "normal_weight")

        # Overweight: 25.0 <= BMI < 30.0
        bmi_o, cat_o = calculate_bmi(weight_kg=85.0, height_cm=175.0)
        self.assertEqual(bmi_o, 27.76)
        self.assertEqual(cat_o, "overweight")

        # Obesity Class 1: 30.0 <= BMI < 35.0
        bmi_1, cat_1 = calculate_bmi(weight_kg=95.0, height_cm=175.0)
        self.assertEqual(bmi_1, 31.02)
        self.assertEqual(cat_1, "obesity_class_1")

        # Obesity Class 2: 35.0 <= BMI < 40.0
        bmi_2, cat_2 = calculate_bmi(weight_kg=110.0, height_cm=175.0)
        self.assertEqual(bmi_2, 35.92)
        self.assertEqual(cat_2, "obesity_class_2")

        # Obesity Class 3: BMI >= 40.0
        bmi_3, cat_3 = calculate_bmi(weight_kg=130.0, height_cm=175.0)
        self.assertEqual(bmi_3, 42.45)
        self.assertEqual(cat_3, "obesity_class_3")

    def test_bmr_mifflin_st_jeor_equations(self) -> None:
        # Male: 10*80 + 6.25*182 - 5*28 + 5 = 800 + 1137.5 - 140 + 5 = 1802.5
        bmr_male = calculate_bmr(weight_kg=80.0, height_cm=182.0, age_years=28, sex="male")
        self.assertEqual(bmr_male, 1802.5)

        # Female: 10*65 + 6.25*168 - 5*30 - 161 = 650 + 1050 - 150 - 161 = 1389.0
        bmr_female = calculate_bmr(weight_kg=65.0, height_cm=168.0, age_years=30, sex="female")
        self.assertEqual(bmr_female, 1389.0)

        # Omitted sex: must return None
        bmr_none = calculate_bmr(weight_kg=80.0, height_cm=182.0, age_years=28, sex=None)
        self.assertIsNone(bmr_none)

    def test_calculate_biometrics_endpoint_full_male(self) -> None:
        payload = {
            "age_years": 28,
            "sex_for_equation": "male",
            "height_cm": 182.0,
            "weight_kg": 80.0,
            "activity_level": "moderately_active",
            "goal": "maintain",
        }
        resp = self.client.post("/api/v1/biometrics/calculate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["bmi"], 24.15)
        self.assertEqual(data["bmi_category"], "normal_weight")
        self.assertEqual(data["bmr_kcal"], 1802.5)
        self.assertEqual(data["tdee_kcal"], 2793.88)
        self.assertEqual(data["target_calories_kcal"], 2794)
        self.assertEqual(data["formula"], "mifflin_st_jeor")
        self.assertEqual(data["activity_multiplier"], 1.55)
        self.assertEqual(data["goal"], "maintain")
        self.assertEqual(data["goal_adjustment_kcal"], 0)

        macros = data["macro_targets_grams"]
        self.assertEqual(macros["protein_g"], 140)
        self.assertEqual(macros["carbohydrates_g"], 349)
        self.assertEqual(macros["fat_g"], 93)

        self.assertIn("disclaimer", data)
        self.assertIn("caveats", data)

    def test_calculate_biometrics_endpoint_omitted_sex(self) -> None:
        payload = {
            "age_years": 32,
            "height_cm": 170.0,
            "weight_kg": 68.0,
            "activity_level": "lightly_active",
            "goal": "maintain",
        }
        resp = self.client.post("/api/v1/biometrics/calculate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # BMI must be calculated
        self.assertEqual(data["bmi"], 23.53)
        self.assertEqual(data["bmi_category"], "normal_weight")

        # Metabolic values must remain strictly NULL (zero fabrication)
        self.assertIsNone(data["bmr_kcal"])
        self.assertIsNone(data["tdee_kcal"])
        self.assertIsNone(data["target_calories_kcal"])
        self.assertIsNone(data["activity_multiplier"])
        self.assertIsNone(data["goal_adjustment_kcal"])
        self.assertIsNone(data["macro_targets_grams"])

    def test_calculate_biometrics_activity_multipliers(self) -> None:
        multipliers = {
            "sedentary": 1.2,
            "lightly_active": 1.375,
            "moderately_active": 1.55,
            "very_active": 1.725,
            "extra_active": 1.9,
        }
        for level, mult in multipliers.items():
            payload = {
                "age_years": 30,
                "sex_for_equation": "male",
                "height_cm": 180.0,
                "weight_kg": 75.0,
                "activity_level": level,
                "goal": "maintain",
            }
            resp = self.client.post("/api/v1/biometrics/calculate", json=payload)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["activity_multiplier"], mult)
            expected_tdee = round(data["bmr_kcal"] * mult, 2)
            self.assertEqual(data["tdee_kcal"], expected_tdee)

    def test_calculate_biometrics_goal_adjustments(self) -> None:
        # Lose goal: -400 kcal
        resp_lose = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 25,
                "sex_for_equation": "female",
                "height_cm": 165.0,
                "weight_kg": 70.0,
                "activity_level": "moderately_active",
                "goal": "lose",
            },
        )
        self.assertEqual(resp_lose.status_code, 200)
        data_lose = resp_lose.json()
        self.assertEqual(data_lose["goal_adjustment_kcal"], -400)
        self.assertEqual(
            data_lose["target_calories_kcal"], round(data_lose["tdee_kcal"] - 400)
        )

        # Gain goal: +400 kcal
        resp_gain = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 25,
                "sex_for_equation": "female",
                "height_cm": 165.0,
                "weight_kg": 70.0,
                "activity_level": "moderately_active",
                "goal": "gain",
            },
        )
        self.assertEqual(resp_gain.status_code, 200)
        data_gain = resp_gain.json()
        self.assertEqual(data_gain["goal_adjustment_kcal"], 400)
        self.assertEqual(
            data_gain["target_calories_kcal"], round(data_gain["tdee_kcal"] + 400)
        )

    def test_calculate_biometrics_minimum_calorie_floor(self) -> None:
        # Small person with high deficit should never be prescribed < 1200 kcal
        resp = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 60,
                "sex_for_equation": "female",
                "height_cm": 150.0,
                "weight_kg": 42.0,
                "activity_level": "sedentary",
                "goal": "lose",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["target_calories_kcal"], 1200)

    def test_biometrics_validation_errors(self) -> None:
        # Invalid age (< 1)
        r_age = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 0,
                "height_cm": 170.0,
                "weight_kg": 70.0,
                "activity_level": "sedentary",
            },
        )
        self.assertEqual(r_age.status_code, 400)
        self.assertEqual(r_age.json()["error"]["code"], "VALIDATION_ERROR")

        # Invalid height (< 50 cm)
        r_height = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 25,
                "height_cm": 45.0,
                "weight_kg": 70.0,
                "activity_level": "sedentary",
            },
        )
        self.assertEqual(r_height.status_code, 400)

        # Invalid weight (< 20 kg)
        r_weight = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 25,
                "height_cm": 170.0,
                "weight_kg": 15.0,
                "activity_level": "sedentary",
            },
        )
        self.assertEqual(r_weight.status_code, 400)


class TestUSDAFoodDataEndpoints(unittest.TestCase):
    """Test USDA FoodData Central search and detail endpoints against live database."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_search_usda_foods_returns_results(self) -> None:
        resp = self.client.get("/api/v1/nutrition/foods/search?q=oats&limit=10")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("data", data)
        self.assertIn("pagination", data)

        pagination = data["pagination"]
        self.assertEqual(pagination["page"], 1)
        self.assertEqual(pagination["limit"], 10)
        self.assertGreater(pagination["total_items"], 0)
        self.assertGreater(pagination["total_pages"], 0)

        foods = data["data"]
        self.assertLessEqual(len(foods), 10)
        for f in foods:
            self.assertIsInstance(f["fdc_id"], int)
            self.assertEqual(f["data_type"], "sr_legacy_food")
            self.assertIn("oats", f["description"].lower())

    def test_search_usda_foods_no_results(self) -> None:
        resp = self.client.get(
            "/api/v1/nutrition/foods/search?q=xyznonexistentfood987654"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["data"], [])
        self.assertEqual(data["pagination"]["total_items"], 0)
        self.assertEqual(data["pagination"]["total_pages"], 0)

    def test_search_usda_foods_empty_q_returns_400(self) -> None:
        resp = self.client.get("/api/v1/nutrition/foods/search?q=")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "VALIDATION_ERROR")

    def test_search_usda_foods_pagination_boundaries(self) -> None:
        r1 = self.client.get("/api/v1/nutrition/foods/search?q=egg&limit=5&page=1")
        r2 = self.client.get("/api/v1/nutrition/foods/search?q=egg&limit=5&page=2")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        ids1 = [f["fdc_id"] for f in r1.json()["data"]]
        ids2 = [f["fdc_id"] for f in r2.json()["data"]]
        self.assertEqual(len(ids1), 5)
        self.assertEqual(len(ids2), 5)
        # Ensure distinct pages
        self.assertEqual(len(set(ids1).intersection(set(ids2))), 0)

    def test_get_usda_food_detail_existing(self) -> None:
        resp = self.client.get("/api/v1/nutrition/foods/169705")
        self.assertEqual(resp.status_code, 200)
        food = resp.json()

        self.assertEqual(food["fdc_id"], 169705)
        self.assertEqual(food["data_type"], "sr_legacy_food")
        self.assertIn("Oats", food["description"])

        # Nutrients per 100g verification
        nutrients = food["nutrients"]
        self.assertGreater(len(nutrients), 0)
        protein_meas = next((n for n in nutrients if n["nutrient_id"] == 1003), None)
        self.assertIsNotNone(protein_meas)
        self.assertEqual(protein_meas["name"], "Protein")
        self.assertEqual(protein_meas["unit_name"], "G")
        self.assertEqual(protein_meas["amount_per_100g"], 16.89)

        # Portions verification
        portions = food["portions"]
        self.assertGreater(len(portions), 0)
        cup_portion = portions[0]
        self.assertEqual(cup_portion["gram_weight"], 156.0)

    def test_get_usda_food_detail_not_found_returns_404(self) -> None:
        resp = self.client.get("/api/v1/nutrition/foods/99999999")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "HTTP_404")
        self.assertIn("was not found", data["error"]["message"])


class TestRecipeNutritionEstimation(unittest.TestCase):
    """Test recipe nutrition estimation engine and caching endpoints."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_estimate_nutrition_fully_mapped(self) -> None:
        payload = {
            "servings": 2,
            "ingredients": [
                {
                    "raw_text": "2 cups whole rolled oats",
                    "canonical_name": "rolled oats",
                    "quantity": 2.0,
                    "unit": "cup",
                    "quantity_g": 160.0,
                    "fdc_id": 169705,
                }
            ],
        }
        resp = self.client.post("/api/v1/nutrition/recipes/estimate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["status"], "calculated")
        self.assertEqual(data["servings"], 2)

        cov = data["ingredient_coverage"]
        self.assertEqual(cov["mapped_count"], 1)
        self.assertEqual(cov["total_count"], 1)
        self.assertEqual(cov["coverage_pct"], 100.0)

        totals = data["totals"]
        self.assertIsNotNone(totals)
        self.assertGreater(totals["calories_kcal"], 0)
        self.assertGreater(totals["protein_g"], 0)

        per_serving = data["per_serving"]
        self.assertIsNotNone(per_serving)
        self.assertAlmostEqual(
            per_serving["calories_kcal"] * 2, totals["calories_kcal"], delta=1.0
        )

        self.assertEqual(data["unmapped_ingredients"], [])
        self.assertIn("Aggregated from USDA FoodData Central", data["provenance_note"])

    def test_estimate_nutrition_partially_mapped(self) -> None:
        payload = {
            "servings": 1,
            "ingredients": [
                {
                    "raw_text": "100g rolled oats",
                    "quantity_g": 100.0,
                    "fdc_id": 169705,
                },
                {
                    "raw_text": "1 pinch exotic unlisted mystery flower",
                },
            ],
        }
        resp = self.client.post("/api/v1/nutrition/recipes/estimate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # 1 out of 2 mapped -> 50% coverage -> "partial"
        self.assertEqual(data["status"], "partial")
        self.assertEqual(data["ingredient_coverage"]["coverage_pct"], 50.0)
        self.assertIn(
            "1 pinch exotic unlisted mystery flower", data["unmapped_ingredients"]
        )

    def test_estimate_nutrition_completely_unmapped(self) -> None:
        payload = {
            "servings": 1,
            "ingredients": [
                {"raw_text": "unmapped imaginary root"},
                {"raw_text": "unmapped space seasoning"},
            ],
        }
        resp = self.client.post("/api/v1/nutrition/recipes/estimate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["status"], "uncalculated")
        self.assertEqual(data["ingredient_coverage"]["coverage_pct"], 0.0)
        self.assertIsNone(data["totals"])
        self.assertIsNone(data["per_serving"])
        self.assertEqual(len(data["unmapped_ingredients"]), 2)

    def test_usda_lookup_safety_against_arbitrary_prefix_matches(self) -> None:
        """Nutritionally ambiguous terms must not resolve automatically via unsafe prefix matching."""
        from services.profile_nutrition.database import get_db_manager
        from services.profile_nutrition.repository import ProfileRepository
        repo = ProfileRepository(get_db_manager())

        unsafe_probe_terms = [
            "pepper",        # Must NOT resolve to peppermint
            "milk",          # Must NOT resolve to sheep milk
            "tomato",        # Must NOT resolve to tomato powder
            "garlic powder", # Must NOT resolve to fresh garlic
            "skim milk",     # Must NOT resolve to whole milk
        ]
        for term in unsafe_probe_terms:
            fdc = repo.find_fdc_id_by_name(term)
            self.assertIsNone(
                fdc,
                f"Unsafe prefix match detected! '{term}' resolved to FDC ID {fdc} instead of None",
            )

    def test_estimate_nutrition_unsafe_prefix_terms_remain_unmapped(self) -> None:
        """Ingredients with ambiguous names remain in unmapped_ingredients and do not fabricate nutrition."""
        payload = {
            "servings": 1,
            "ingredients": [
                {
                    "raw_text": "1 tsp black pepper",
                    "canonical_name": "pepper",
                    "quantity": 1.0,
                    "unit": "tsp",
                },
                {
                    "raw_text": "1 cup milk",
                    "canonical_name": "milk",
                    "quantity": 1.0,
                    "unit": "cup",
                },
            ],
        }
        resp = self.client.post("/api/v1/nutrition/recipes/estimate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "uncalculated")
        self.assertEqual(data["ingredient_coverage"]["coverage_pct"], 0.0)
        self.assertIsNone(data["totals"])
        self.assertEqual(len(data["unmapped_ingredients"]), 2)
        self.assertIn("1 tsp black pepper", data["unmapped_ingredients"])
        self.assertIn("1 cup milk", data["unmapped_ingredients"])

    def test_cached_recipe_nutrition_not_found_returns_404(self) -> None:
        resp = self.client.get("/api/v1/nutrition/recipes/rcp_nlg_108294")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertEqual(data["error"]["code"], "HTTP_404")
        self.assertIn("No nutrition estimate cached", data["error"]["message"])

    def test_cached_recipe_nutrition_invalid_id_pattern_returns_400(self) -> None:
        resp = self.client.get("/api/v1/nutrition/recipes/invalid_pattern_recipe")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["error"]["code"], "VALIDATION_ERROR")


class TestMacronutrientDistributionConsistency(unittest.TestCase):
    """Deterministic validation of the 20% protein / 50% carbs / 30% fat distribution."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def test_case_a_reference_2000_kcal_targets(self) -> None:
        """Test Case A: 2,000 kcal yields 100g protein, 250g carbs, 67g fat (approx 66.7g)."""
        from services.profile_nutrition.calculator import calculate_macro_targets
        macros = calculate_macro_targets(2000)

        # Gram targets
        self.assertEqual(macros.protein_g, 100)
        self.assertEqual(macros.carbohydrates_g, 250)
        self.assertEqual(macros.fat_g, 67)

        # Unrounded fat gram check
        unrounded_fat = (2000 * 0.30) / 9.0
        self.assertAlmostEqual(unrounded_fat, 66.7, places=1)

        # Percentage split
        self.assertEqual(macros.protein_pct, 20.0)
        self.assertEqual(macros.carbohydrates_pct, 50.0)
        self.assertEqual(macros.fat_pct, 30.0)

        # Energy allocation sum before integer rounding
        energy_sum = (macros.protein_g * 4.0) + (macros.carbohydrates_g * 4.0) + (unrounded_fat * 9.0)
        self.assertAlmostEqual(energy_sum, 2000.0, places=4)

    def test_case_b_reference_2400_kcal_targets(self) -> None:
        """Test Case B: 2,400 kcal yields exactly 120g protein, 300g carbs, 80g fat."""
        from services.profile_nutrition.calculator import calculate_macro_targets
        macros = calculate_macro_targets(2400)

        self.assertEqual(macros.protein_g, 120)
        self.assertEqual(macros.carbohydrates_g, 300)
        self.assertEqual(macros.fat_g, 80)

        # Energy allocation sum
        energy_sum = (macros.protein_g * 4.0) + (macros.carbohydrates_g * 4.0) + (macros.fat_g * 9.0)
        self.assertEqual(energy_sum, 2400.0)

    def test_case_c_calorie_floor_macro_derivation(self) -> None:
        """Test Case C: Small individual with high deficit is clamped to 1,200 kcal floor and macros derive from it."""
        resp = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 65,
                "sex_for_equation": "female",
                "height_cm": 145.0,
                "weight_kg": 40.0,
                "activity_level": "sedentary",
                "goal": "lose",  # -400 kcal would push well below 1200
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["target_calories_kcal"], 1200)

        macros = data["macro_targets_grams"]
        # 1200 * 0.20 / 4 = 60g protein
        self.assertEqual(macros["protein_g"], 60)
        # 1200 * 0.50 / 4 = 150g carbs
        self.assertEqual(macros["carbohydrates_g"], 150)
        # 1200 * 0.30 / 9 = 40g fat
        self.assertEqual(macros["fat_g"], 40)

        # Sum of energy at floor
        self.assertEqual(60 * 4 + 150 * 4 + 40 * 9, 1200)

    def test_case_d_different_activity_levels_scale_macros_proportionally(self) -> None:
        """Test Case D: Activity multipliers scale TDEE and macro grams proportionally while keeping 20/50/30 split."""
        activity_levels = ["sedentary", "lightly_active", "moderately_active", "very_active", "extra_active"]
        for level in activity_levels:
            resp = self.client.post(
                "/api/v1/biometrics/calculate",
                json={
                    "age_years": 30,
                    "sex_for_equation": "male",
                    "height_cm": 178.0,
                    "weight_kg": 75.0,
                    "activity_level": level,
                    "goal": "maintain",
                },
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            target_kcal = data["target_calories_kcal"]
            macros = data["macro_targets_grams"]

            expected_protein = round((target_kcal * 0.20) / 4.0)
            expected_carbs = round((target_kcal * 0.50) / 4.0)
            expected_fat = round((target_kcal * 0.30) / 9.0)

            self.assertEqual(macros["protein_g"], expected_protein)
            self.assertEqual(macros["carbohydrates_g"], expected_carbs)
            self.assertEqual(macros["fat_g"], expected_fat)

    def test_case_e_maintain_lose_gain_goal_macro_behavior(self) -> None:
        """Test Case E: Maintain (0), Lose (-400), and Gain (+400) maintain 20/50/30 distribution."""
        base_payload = {
            "age_years": 28,
            "sex_for_equation": "female",
            "height_cm": 165.0,
            "weight_kg": 62.0,
            "activity_level": "moderately_active",
        }
        for goal, expected_adj in [("maintain", 0), ("lose", -400), ("gain", 400)]:
            p = dict(base_payload, goal=goal)
            resp = self.client.post("/api/v1/biometrics/calculate", json=p)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["goal_adjustment_kcal"], expected_adj)
            target = data["target_calories_kcal"]
            macros = data["macro_targets_grams"]

            self.assertEqual(macros["protein_g"], round((target * 0.20) / 4.0))
            self.assertEqual(macros["carbohydrates_g"], round((target * 0.50) / 4.0))
            self.assertEqual(macros["fat_g"], round((target * 0.30) / 9.0))

    def test_case_f_missing_biological_sex_omits_macros_and_bmr(self) -> None:
        """Test Case F: When sex_for_equation is omitted, BMI is calculated, but BMR, TDEE, and macros remain NULL."""
        resp = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 35,
                "height_cm": 175.0,
                "weight_kg": 72.0,
                "activity_level": "moderately_active",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNotNone(data["bmi"])
        self.assertEqual(data["bmi_category"], "normal_weight")
        self.assertIsNone(data["bmr_kcal"])
        self.assertIsNone(data["tdee_kcal"])
        self.assertIsNone(data["target_calories_kcal"])
        self.assertIsNone(data["macro_targets_grams"])
        self.assertTrue(any("Biological sex was omitted" in c for c in data["caveats"]))

    def test_case_g_macro_percentages_sum_to_100_percent_invariant(self) -> None:
        """Test Case G: Authoritative macro percentages sum to exactly 100.0% without residual 5% gap."""
        from services.profile_nutrition.calculator import (
            DEFAULT_PROTEIN_PCT,
            DEFAULT_CARBS_PCT,
            DEFAULT_FAT_PCT,
        )
        total = DEFAULT_PROTEIN_PCT + DEFAULT_CARBS_PCT + DEFAULT_FAT_PCT
        self.assertAlmostEqual(total, 100.0, places=6)
        self.assertEqual(DEFAULT_PROTEIN_PCT, 20.0)
        self.assertEqual(DEFAULT_CARBS_PCT, 50.0)
        self.assertEqual(DEFAULT_FAT_PCT, 30.0)

    def test_case_h_api_response_structure_and_corrected_distribution(self) -> None:
        """Test Case H: Live endpoint exposes corrected targets with exact response schema and caveat."""
        resp = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 28,
                "sex_for_equation": "male",
                "height_cm": 182.0,
                "weight_kg": 80.0,
                "activity_level": "moderately_active",
                "goal": "maintain",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Schema keys present
        expected_keys = {
            "bmi", "bmi_category", "bmr_kcal", "tdee_kcal", "target_calories_kcal",
            "formula", "activity_multiplier", "goal", "goal_adjustment_kcal",
            "macro_targets_grams", "macro_ranges_percent", "caveats", "disclaimer",
        }
        self.assertTrue(expected_keys.issubset(data.keys()))

        # Corrected fat targets
        macros = data["macro_targets_grams"]
        self.assertEqual(macros["protein_g"], 140)
        self.assertEqual(macros["carbohydrates_g"], 349)
        self.assertEqual(macros["fat_g"], 93)  # Corrected from 78

        # Caveat mentions 20% protein, 50% carbohydrates, 30% fat
        caveat_text = " ".join(data["caveats"])
        self.assertIn("20% protein", caveat_text)
        self.assertIn("50% carbohydrates", caveat_text)
        self.assertIn("30% fat", caveat_text)

        # AMDR ranges remain separate reference ranges
        ranges = data["macro_ranges_percent"]
        self.assertEqual(ranges["protein"]["min_pct"], 10)
        self.assertEqual(ranges["protein"]["max_pct"], 35)
        self.assertEqual(ranges["fat"]["min_pct"], 20)
        self.assertEqual(ranges["fat"]["max_pct"], 35)

    def test_case_i_no_fabricated_nutrition_preserves_usda_and_recipe_estimates(self) -> None:
        """Test Case I: Biometric target correction does not alter measured USDA food or recipe nutrition data."""
        # Query known USDA food (oats: 169705)
        resp = self.client.get("/api/v1/nutrition/foods/169705")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["fdc_id"], 169705)
        # Verify measured nutrients per 100g are from USDA SR Legacy, not fabricated 20/50/30
        nutrients_by_id = {n["nutrient_id"]: n["amount_per_100g"] for n in data["nutrients"]}
        self.assertIn(1008, nutrients_by_id)  # Calories
        self.assertIn(1003, nutrients_by_id)  # Protein
        self.assertIn(1004, nutrients_by_id)  # Total lipid (fat)
        self.assertIn(1005, nutrients_by_id)  # Carbohydrate
        self.assertEqual(nutrients_by_id[1003], 16.89)  # Oats protein 16.89g per 100g

    def test_case_j_age_applicability_pediatric_caveat(self) -> None:
        """Test Case J: When age < 18, a pediatric applicability caveat is attached."""
        resp_minor = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 14,
                "sex_for_equation": "male",
                "height_cm": 160.0,
                "weight_kg": 50.0,
                "activity_level": "moderately_active",
            },
        )
        self.assertEqual(resp_minor.status_code, 200)
        caveats_minor = resp_minor.json()["caveats"]
        self.assertTrue(any("pediatric" in c.lower() for c in caveats_minor))

        resp_adult = self.client.post(
            "/api/v1/biometrics/calculate",
            json={
                "age_years": 25,
                "sex_for_equation": "male",
                "height_cm": 180.0,
                "weight_kg": 75.0,
                "activity_level": "moderately_active",
            },
        )
        self.assertEqual(resp_adult.status_code, 200)
        caveats_adult = resp_adult.json()["caveats"]
        self.assertFalse(any("pediatric" in c.lower() for c in caveats_adult))


class TestSecurityAndRoleIsolation(unittest.TestCase):
    """Test database role boundaries and schema isolation for Profile Service."""

    def test_profile_service_cannot_query_other_schemas(self) -> None:
        profile_url = os.environ.get("PROFILE_SERVICE_DATABASE_URL")
        self.assertIsNotNone(profile_url)

        with psycopg.connect(profile_url) as conn:
            with conn.cursor() as cur:
                # Allowed on profile_nutrition
                cur.execute("SELECT COUNT(*) FROM profile_nutrition.usda_foods;")
                self.assertEqual(cur.fetchone()[0], 7793)

                # Denied on recipe_catalog
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM recipe_catalog.recipes LIMIT 1;")
                conn.rollback()

                # Denied on meal_planner
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute("SELECT 1 FROM meal_planner.guest_sessions LIMIT 1;")
                conn.rollback()


if __name__ == "__main__":
    unittest.main()

