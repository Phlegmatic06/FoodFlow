import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { routes } from '../router';
import { ThemeProvider } from '../theme/ThemeContext';
import {
  BiometricsCalculationResponse,
  PaginatedUSDAFoodSummary,
  USDAFoodDetail,
  RecipeNutritionEstimateResponse,
} from '../api/types/profile';
import { RecipeDetail } from '../api/types/recipe';

// ============================================================================
// Mock Data Sets
// ============================================================================

const defaultRanges = {
  protein: { min_pct: 10, max_pct: 35 },
  carbohydrates: { min_pct: 45, max_pct: 65 },
  fat: { min_pct: 20, max_pct: 35 },
};

const mockMaleBiometricsResponse: BiometricsCalculationResponse = {
  bmi: 24.69,
  bmi_category: 'normal_weight',
  bmr_kcal: 1780.0,
  tdee_kcal: 2136.0,
  target_calories_kcal: 2136.0,
  formula: 'mifflin_st_jeor',
  activity_multiplier: 1.2,
  goal: 'maintain',
  goal_adjustment_kcal: 0,
  macro_targets_grams: {
    protein_g: 107.0,
    carbohydrates_g: 267.0,
    fat_g: 71.0,
  },
  macro_ranges_percent: defaultRanges,
  caveats: [],
  disclaimer: 'Nutritional estimates are for educational guidance only.',
};

const mockFemaleBiometricsResponse: BiometricsCalculationResponse = {
  bmi: 22.0,
  bmi_category: 'normal_weight',
  bmr_kcal: 1450.0,
  tdee_kcal: 1740.0,
  target_calories_kcal: 1740.0,
  formula: 'mifflin_st_jeor',
  activity_multiplier: 1.2,
  goal: 'maintain',
  goal_adjustment_kcal: 0,
  macro_targets_grams: {
    protein_g: 87.0,
    carbohydrates_g: 218.0,
    fat_g: 58.0,
  },
  macro_ranges_percent: defaultRanges,
  caveats: [],
  disclaimer: 'Nutritional estimates are for educational guidance only.',
};

const mockOmittedSexBiometricsResponse: BiometricsCalculationResponse = {
  bmi: 24.69,
  bmi_category: 'normal_weight',
  bmr_kcal: null,
  tdee_kcal: null,
  target_calories_kcal: null,
  formula: 'omitted_sex',
  activity_multiplier: null,
  goal: 'maintain',
  goal_adjustment_kcal: null,
  macro_targets_grams: null,
  macro_ranges_percent: defaultRanges,
  caveats: ['BMR and TDEE equations require sex-specific metabolic constants.'],
  disclaimer: 'Nutritional estimates are for educational guidance only.',
};

const mockWeightLossResponse: BiometricsCalculationResponse = {
  bmi: 27.5,
  bmi_category: 'overweight',
  bmr_kcal: 1800.0,
  tdee_kcal: 2400.0,
  target_calories_kcal: 2000.0, // 2400 - 400
  formula: 'mifflin_st_jeor',
  activity_multiplier: 1.333,
  goal: 'lose',
  goal_adjustment_kcal: -400,
  macro_targets_grams: {
    protein_g: 100.0,
    carbohydrates_g: 250.0,
    fat_g: 67.0,
  },
  macro_ranges_percent: defaultRanges,
  caveats: [],
  disclaimer: 'Nutritional estimates are for educational guidance only.',
};

const mockUSDASearchResultsPage1: PaginatedUSDAFoodSummary = {
  data: [
    {
      fdc_id: 171077,
      description: 'Chicken, broilers or fryers, breast, meat only, cooked, roasted',
      data_type: 'sr_legacy',
    },
    {
      fdc_id: 171078,
      description: 'Chicken, broilers or fryers, breast, meat only, raw',
      data_type: 'sr_legacy',
    },
  ],
  pagination: {
    page: 1,
    limit: 10,
    total_items: 25,
    total_pages: 3,
  },
};

const mockUSDASearchResultsPage2: PaginatedUSDAFoodSummary = {
  data: [
    {
      fdc_id: 171079,
      description: 'Chicken, broilers or fryers, drumstick, meat only, cooked, roasted',
      data_type: 'sr_legacy',
    },
  ],
  pagination: {
    page: 2,
    limit: 10,
    total_items: 25,
    total_pages: 3,
  },
};

const mockEmptyUSDASearchResults: PaginatedUSDAFoodSummary = {
  data: [],
  pagination: {
    page: 1,
    limit: 10,
    total_items: 0,
    total_pages: 0,
  },
};

const mockUSDAFoodDetail: USDAFoodDetail = {
  fdc_id: 171077,
  description: 'Chicken, broilers or fryers, breast, meat only, cooked, roasted',
  data_type: 'sr_legacy',
  publication_date: '2019-04-01',
  nutrients: [
    {
      nutrient_id: 1008,
      name: 'Energy',
      amount_per_100g: 165.0,
      unit_name: 'kcal',
      data_points: 12,
    },
    {
      nutrient_id: 1003,
      name: 'Protein',
      amount_per_100g: 31.02,
      unit_name: 'g',
      data_points: 8,
    },
    {
      nutrient_id: 1004,
      name: 'Total lipid (fat)',
      amount_per_100g: 3.57,
      unit_name: 'g',
      data_points: 10,
    },
    {
      nutrient_id: 1005,
      name: 'Carbohydrate, by difference',
      amount_per_100g: 0.0,
      unit_name: 'g',
      data_points: 5,
    },
    {
      nutrient_id: 1079,
      name: 'Fiber, total dietary',
      amount_per_100g: null,
      unit_name: 'g',
      data_points: 0,
    },
  ],
  portions: [
    {
      id: 1,
      gram_weight: 86.0,
      amount: 1.0,
      portion_description: '1 breast, bone and skin removed',
    },
    {
      id: 2,
      gram_weight: 140.0,
      amount: 1.0,
      portion_description: '1 cup, chopped or diced',
    },
  ],
};

const mockRecipeDetailForEstimator: RecipeDetail = {
  id: 'rcp_foodcom_358911',
  source_dataset: 'food_com',
  source_id: '358911',
  title: 'Skillet Garlic Chicken Breast',
  description: 'Savory chicken skillet recipe.',
  servings: 4,
  prep_time_minutes: 10,
  cook_time_minutes: 20,
  total_time_minutes: 30,
  ingredients: [
    {
      position: 1,
      raw_text: '4 boneless skinless chicken breasts',
      canonical_ingredient_id: 101,
      canonical_name: 'chicken breast',
      quantity: 4,
      unit: 'pieces',
    },
    {
      position: 2,
      raw_text: '2 tbsp olive oil',
      canonical_ingredient_id: 50,
      canonical_name: 'olive oil',
      quantity: 2,
      unit: 'tbsp',
    },
    {
      position: 3,
      raw_text: '3 cloves garlic, minced',
      canonical_ingredient_id: 10,
      canonical_name: 'garlic clove',
      quantity: 3,
      unit: 'cloves',
    },
  ],
  instructions: [
    { step_number: 1, instruction: 'Heat olive oil in large skillet over medium heat.' },
  ],
  raw_nutrition: null,
  created_at: '2026-11-03T07:00:00Z',
  rating_count: 12,
  tags: ['chicken', 'dinner'],
};

const mockRecipeEstimateSuccess: RecipeNutritionEstimateResponse = {
  status: 'calculated',
  ingredient_coverage: {
    total_count: 3,
    mapped_count: 3,
    coverage_pct: 100.0,
  },
  servings: 4,
  totals: {
    calories_kcal: 1480.0,
    protein_g: 132.0,
    total_fat_g: 36.0,
    saturated_fat_g: 5.2,
    carbohydrates_g: 4.8,
    fiber_g: 0.6,
    sodium_mg: 480.0,
  },
  per_serving: {
    calories_kcal: 370.0,
    protein_g: 33.0,
    total_fat_g: 9.0,
    saturated_fat_g: 1.3,
    carbohydrates_g: 1.2,
    fiber_g: 0.2,
    sodium_mg: 120.0,
  },
  unmapped_ingredients: [],
  provenance_note: 'Aggregated from USDA SR Legacy database (items: 101, 50, 10).',
  disclaimer: 'Nutritional values are mathematical estimates based on USDA food composition data.',
};

const mockRecipeEstimatePartial: RecipeNutritionEstimateResponse = {
  status: 'partial',
  ingredient_coverage: {
    total_count: 4,
    mapped_count: 2,
    coverage_pct: 50.0,
  },
  servings: 2,
  totals: {
    calories_kcal: 500.0,
    protein_g: 30.0,
    total_fat_g: 12.0,
    saturated_fat_g: 2.0,
    carbohydrates_g: 40.0,
    fiber_g: 4.0,
    sodium_mg: 280.0,
  },
  per_serving: {
    calories_kcal: 250.0,
    protein_g: 15.0,
    total_fat_g: 6.0,
    saturated_fat_g: 1.0,
    carbohydrates_g: 20.0,
    fiber_g: 2.0,
    sodium_mg: 140.0,
  },
  unmapped_ingredients: ['2 pinches exotic herb blend', 'secret spice rub'],
  provenance_note: 'Partial estimate: 2 ingredients could not be matched.',
  disclaimer: 'Nutritional values are mathematical estimates based on USDA food composition data.',
};

// ============================================================================
// Mock Fetch Router Setup
// ============================================================================

interface MockFetchOptions {
  biometricsResponse?: BiometricsCalculationResponse;
  biometricsStatus?: number;
  usdaSearchResponse?: PaginatedUSDAFoodSummary;
  usdaSearchStatus?: number;
  usdaFoodDetail?: USDAFoodDetail;
  usdaDetailStatus?: number;
  recipeDetail?: RecipeDetail;
  recipeDetailStatus?: number;
  recipeEstimateResponse?: RecipeNutritionEstimateResponse;
  recipeEstimateStatus?: number;
  cachedNutritionStatus?: number;
}

function setupMockFetch(options: MockFetchOptions = {}) {
  const {
    biometricsResponse = mockMaleBiometricsResponse,
    biometricsStatus = 200,
    usdaSearchResponse = mockUSDASearchResultsPage1,
    usdaSearchStatus = 200,
    usdaFoodDetail = mockUSDAFoodDetail,
    usdaDetailStatus = 200,
    recipeDetail = mockRecipeDetailForEstimator,
    recipeDetailStatus = 200,
    recipeEstimateResponse = mockRecipeEstimateSuccess,
    recipeEstimateStatus = 200,
    cachedNutritionStatus = 404,
  } = options;

  return vi.fn().mockImplementation((url: string | URL) => {
    const urlStr = url.toString();

    // 1. Biometrics calculation
    if (urlStr.includes('/api/v1/biometrics/calculate')) {
      if (biometricsStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => biometricsResponse,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: biometricsStatus,
          statusText: 'Internal Server Error',
          json: async () => ({
            error: {
              code: 'CALCULATION_FAILED',
              message: 'Metabolic calculation failed in mathematical engine.',
            },
          }),
        });
      }
    }

    // 2. USDA Food Search
    if (urlStr.includes('/api/v1/nutrition/foods/search')) {
      if (usdaSearchStatus === 200) {
        const urlObj = new URL(urlStr);
        const page = urlObj.searchParams.get('page');
        const q = urlObj.searchParams.get('q');
        if (q === 'nonexistentfood') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => mockEmptyUSDASearchResults,
          });
        }
        if (page === '2') {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => mockUSDASearchResultsPage2,
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => usdaSearchResponse,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: usdaSearchStatus,
          statusText: 'Internal Server Error',
          json: async () => ({
            error: {
              code: 'USDA_SEARCH_ERROR',
              message: 'Failed to search USDA food items.',
            },
          }),
        });
      }
    }

    // 3. USDA Food Detail by FDC ID
    if (urlStr.match(/\/api\/v1\/nutrition\/foods\/\d+/)) {
      if (usdaDetailStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => usdaFoodDetail,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: usdaDetailStatus,
          statusText: 'Not Found',
          json: async () => ({
            error: {
              code: 'FOOD_NOT_FOUND',
              message: 'USDA Food item not found.',
            },
          }),
        });
      }
    }

    // 4. Recipe Detail lookup
    if (urlStr.includes('/api/v1/recipes/')) {
      if (recipeDetailStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => recipeDetail,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: recipeDetailStatus,
          statusText: 'Not Found',
          json: async () => ({
            error: {
              code: 'RECIPE_NOT_FOUND',
              message: 'Recipe not found in catalog.',
            },
          }),
        });
      }
    }

    // 5. Recipe nutrition estimate endpoint
    if (urlStr.includes('/api/v1/nutrition/recipes/estimate')) {
      if (recipeEstimateStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => recipeEstimateResponse,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: recipeEstimateStatus,
          statusText: 'Internal Server Error',
          json: async () => ({
            error: {
              code: 'ESTIMATE_FAILED',
              message: 'Could not calculate recipe nutrition estimation.',
            },
          }),
        });
      }
    }

    // 6. Recipe cached nutrition lookup
    if (urlStr.includes('/api/v1/nutrition/recipes/')) {
      if (cachedNutritionStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            recipe_id: 'rcp_foodcom_358911',
            status: 'calculated',
            calories_kcal: 370.0,
            protein_g: 33.0,
            total_fat_g: 9.0,
            saturated_fat_g: 1.3,
            carbohydrates_g: 1.2,
            fiber_g: 0.2,
            sodium_mg: 120.0,
            ingredient_coverage_pct: 100.0,
            mapped_ingredient_count: 3,
            total_ingredient_count: 3,
            servings: 4,
          }),
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: 404,
          statusText: 'Not Found',
          json: async () => ({
            error: {
              code: 'NUTRITION_NOT_CACHED',
              message: 'No nutrition estimate cached for recipe',
            },
          }),
        });
      }
    }

    return Promise.resolve({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({ error: { message: 'Unhandled mock URL' } }),
    });
  });
}

function renderNutritionPage(initialPath = '/nutrition') {
  const router = createMemoryRouter(routes, {
    initialEntries: [initialPath],
  });

  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

// ============================================================================
// Test Suite: Step 05.4 Nutrition Dashboard & USDA Explorer
// ============================================================================

describe('Nutrition Dashboard, Biometrics Calculator & USDA Food Explorer (Step 05.4)', () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    localStorage.clear();
    sessionStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  // --------------------------------------------------------------------------
  // Group A: Daily Nutrition / Biometrics Calculator
  // --------------------------------------------------------------------------

  it('1. renders all biometric input fields with empty initial values and no pre-filled profiles', async () => {
    global.fetch = setupMockFetch();
    renderNutritionPage();

    expect(screen.getByTestId('biometrics-calculator-section')).toBeInTheDocument();
    expect(screen.getByTestId('calculator-heading')).toHaveTextContent(
      /Daily Nutrition & Biometrics Calculator/i
    );

    const ageInput = screen.getByTestId('input-age') as HTMLInputElement;
    const sexSelect = screen.getByTestId('select-sex') as HTMLSelectElement;
    const heightInput = screen.getByTestId('input-height') as HTMLInputElement;
    const weightInput = screen.getByTestId('input-weight') as HTMLInputElement;
    const activitySelect = screen.getByTestId('select-activity') as HTMLSelectElement;
    const goalSelect = screen.getByTestId('select-goal') as HTMLSelectElement;

    // Check defaults
    expect(ageInput.value).toBe('');
    expect(sexSelect.value).toBe('');
    expect(heightInput.value).toBe('');
    expect(weightInput.value).toBe('');
    expect(activitySelect.value).toBe('moderately_active');
    expect(goalSelect.value).toBe('maintain');

    // Empty state should indicate awaiting input
    expect(screen.getByTestId('results-empty-state')).toBeInTheDocument();
    expect(screen.getByText(/No Biometrics Submitted/i)).toBeInTheDocument();
  });

  it('2. validates required ranges (age 1-120) client-side before calling API', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '150');
    await user.type(screen.getByTestId('input-height'), '175');
    await user.type(screen.getByTestId('input-weight'), '70');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/valid age between 1 and 120/i);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('3. validates height range (50-300 cm) client-side before calling API', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '25');
    await user.type(screen.getByTestId('input-height'), '350');
    await user.type(screen.getByTestId('input-weight'), '70');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/valid height between 50 and 300/i);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('4. validates weight range (20-500 kg) client-side before calling API', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '25');
    await user.type(screen.getByTestId('input-height'), '170');
    await user.type(screen.getByTestId('input-weight'), '10');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/valid weight between 20 and 500/i);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('5. computes complete biometrics for male profile with Mifflin constants', async () => {
    const mockFetch = setupMockFetch({ biometricsResponse: mockMaleBiometricsResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '30');
    await user.selectOptions(screen.getByTestId('select-sex'), 'male');
    await user.type(screen.getByTestId('input-height'), '180');
    await user.type(screen.getByTestId('input-weight'), '80');
    await user.selectOptions(screen.getByTestId('select-activity'), 'sedentary');
    await user.selectOptions(screen.getByTestId('select-goal'), 'maintain');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('results-active-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('result-bmi')).toHaveTextContent('24.69 kg/m²');
    expect(screen.getByTestId('result-bmi-category')).toHaveTextContent(/Normal weight/i);
    expect(screen.getByTestId('result-bmr')).toHaveTextContent('1780 kcal/day');
    expect(screen.getByTestId('result-tdee')).toHaveTextContent('2136 kcal/day');
    expect(screen.getByTestId('result-target-calories')).toHaveTextContent('2136 kcal/day');

    // Verify request payload sent to POST /api/v1/biometrics/calculate
    const call = mockFetch.mock.calls.find((c) =>
      c[0].toString().includes('/api/v1/biometrics/calculate')
    );
    expect(call).toBeDefined();
    const payload = JSON.parse(call![1].body as string);
    expect(payload).toEqual({
      age_years: 30,
      sex_for_equation: 'male',
      height_cm: 180,
      weight_kg: 80,
      activity_level: 'sedentary',
      goal: 'maintain',
    });
  });

  it('6. handles female profile calculation and displays result', async () => {
    const mockFetch = setupMockFetch({ biometricsResponse: mockFemaleBiometricsResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '28');
    await user.selectOptions(screen.getByTestId('select-sex'), 'female');
    await user.type(screen.getByTestId('input-height'), '165');
    await user.type(screen.getByTestId('input-weight'), '60');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('results-active-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('result-bmi')).toHaveTextContent('22 kg/m²');
    expect(screen.getByTestId('result-bmr')).toHaveTextContent('1450 kcal/day');
  });

  it('7. safely handles omitted biological sex: displays BMI but shows BMR/TDEE as Not calculated', async () => {
    const mockFetch = setupMockFetch({ biometricsResponse: mockOmittedSexBiometricsResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '35');
    // Sex left unselected
    await user.type(screen.getByTestId('input-height'), '180');
    await user.type(screen.getByTestId('input-weight'), '80');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('results-active-card')).toBeInTheDocument();
    });

    // BMI calculated
    expect(screen.getByTestId('result-bmi')).toHaveTextContent('24.69 kg/m²');
    // BMR, TDEE, Target must say "Not calculated" (never "0 kcal")
    expect(screen.getByTestId('result-bmr')).toHaveTextContent(/Not calculated/i);
    expect(screen.getByTestId('result-tdee')).toHaveTextContent(/Not calculated/i);
    expect(screen.getByTestId('result-target-calories')).toHaveTextContent(/Not calculated/i);
  });

  it('8. adjusts caloric target with goal selection (-400 kcal for lose)', async () => {
    const mockFetch = setupMockFetch({ biometricsResponse: mockWeightLossResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '40');
    await user.selectOptions(screen.getByTestId('select-sex'), 'male');
    await user.type(screen.getByTestId('input-height'), '175');
    await user.type(screen.getByTestId('input-weight'), '84');
    await user.selectOptions(screen.getByTestId('select-goal'), 'lose');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('results-active-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('result-target-calories')).toHaveTextContent('2000 kcal/day');
  });

  it('9. resets form and returns results view to awaiting input when Clear is clicked', async () => {
    global.fetch = setupMockFetch({ biometricsResponse: mockMaleBiometricsResponse });
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '30');
    await user.type(screen.getByTestId('input-height'), '180');
    await user.type(screen.getByTestId('input-weight'), '80');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('results-active-card')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('clear-biometrics-btn'));

    expect((screen.getByTestId('input-age') as HTMLInputElement).value).toBe('');
    expect((screen.getByTestId('input-height') as HTMLInputElement).value).toBe('');
    expect((screen.getByTestId('input-weight') as HTMLInputElement).value).toBe('');
    expect(screen.getByTestId('results-empty-state')).toBeInTheDocument();
  });

  it('10. handles API failure and provides retry action', async () => {
    const mockFetch = setupMockFetch({ biometricsStatus: 500 });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '30');
    await user.type(screen.getByTestId('input-height'), '180');
    await user.type(screen.getByTestId('input-weight'), '80');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    expect(await screen.findByTestId('calculator-api-error')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group B: Macronutrient Targets Panel
  // --------------------------------------------------------------------------

  it('11. displays baseline educational AMDR breakdown before calculation', async () => {
    global.fetch = setupMockFetch();
    renderNutritionPage();

    const macroPanel = screen.getByTestId('macro-targets-panel');
    expect(macroPanel).toBeInTheDocument();
    expect(screen.getByTestId('macro-guidance-note')).toBeInTheDocument();
    expect(screen.getByTestId('macro-ratio-split')).toHaveTextContent('20% P • 50% C • 30% F');
  });

  it('12. displays calculated macronutrient grams and calorie contributions after biometrics', async () => {
    global.fetch = setupMockFetch({ biometricsResponse: mockMaleBiometricsResponse });
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '30');
    await user.selectOptions(screen.getByTestId('select-sex'), 'male');
    await user.type(screen.getByTestId('input-height'), '180');
    await user.type(screen.getByTestId('input-weight'), '80');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('macro-target-calories')).toHaveTextContent('2136 kcal / day');
    });

    // 20% protein (107g)
    expect(screen.getByTestId('protein-grams')).toHaveTextContent('107g');
    expect(screen.getByTestId('protein-kcal')).toHaveTextContent('~428 kcal');

    // 50% carbs (267g)
    expect(screen.getByTestId('carbs-grams')).toHaveTextContent('267g');
    expect(screen.getByTestId('carbs-kcal')).toHaveTextContent('~1068 kcal');

    // 30% fat (71g)
    expect(screen.getByTestId('fat-grams')).toHaveTextContent('71g');
    expect(screen.getByTestId('fat-kcal')).toHaveTextContent('~639 kcal');
  });

  it('13. renders proportional visual macro distribution bar', async () => {
    global.fetch = setupMockFetch({ biometricsResponse: mockMaleBiometricsResponse });
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '30');
    await user.type(screen.getByTestId('input-height'), '180');
    await user.type(screen.getByTestId('input-weight'), '80');
    await user.selectOptions(screen.getByTestId('select-sex'), 'male');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('macro-bar-carbs')).toBeInTheDocument();
    });

    const carbSegment = screen.getByTestId('macro-bar-carbs');
    const fatSegment = screen.getByTestId('macro-bar-fat');
    const proteinSegment = screen.getByTestId('macro-bar-protein');

    expect(carbSegment).toHaveStyle({ width: '50%' });
    expect(fatSegment).toHaveStyle({ width: '30%' });
    expect(proteinSegment).toHaveStyle({ width: '20%' });
  });

  // --------------------------------------------------------------------------
  // Group C: USDA Food Database Explorer
  // --------------------------------------------------------------------------

  it('14. renders USDA search bar and quick suggestion chips', async () => {
    global.fetch = setupMockFetch();
    renderNutritionPage();

    expect(screen.getByTestId('usda-food-explorer-section')).toBeInTheDocument();
    expect(screen.getByTestId('usda-search-input')).toBeInTheDocument();
    expect(screen.getByTestId('usda-search-btn')).toBeInTheDocument();
    expect(screen.getByTestId('quick-usda-chicken-breast')).toHaveTextContent('chicken breast');
  });

  it('15. clicking a quick search chip populates input and executes search', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    const chip = screen.getByTestId('quick-usda-chicken-breast');
    await user.click(chip);

    expect((screen.getByTestId('usda-search-input') as HTMLInputElement).value).toBe(
      'chicken breast'
    );

    await waitFor(() => {
      expect(screen.getByTestId('usda-foods-list')).toBeInTheDocument();
    });

    expect(screen.getByTestId('usda-item-171077')).toHaveTextContent(
      'Chicken, broilers or fryers, breast, meat only, cooked, roasted'
    );
  });

  it('16. paginates search results with Next and Previous buttons', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    // Trigger search
    await user.type(screen.getByTestId('usda-search-input'), 'chicken');
    await user.click(screen.getByTestId('usda-search-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('usda-page-indicator')).toHaveTextContent('1 / 3');
    });

    const nextBtn = screen.getByTestId('usda-next-page');
    await user.click(nextBtn);

    await waitFor(() => {
      expect(screen.getByTestId('usda-page-indicator')).toHaveTextContent('2 / 3');
    });

    expect(screen.getByText(/Chicken, broilers or fryers, drumstick/i)).toBeInTheDocument();
  });

  it('17. selecting a food item fetches and displays laboratory nutrients per 100g', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('usda-search-input'), 'chicken');
    await user.click(screen.getByTestId('usda-search-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('usda-item-171077')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('usda-item-171077'));

    await waitFor(() => {
      expect(screen.getByTestId('food-detail-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('selected-food-title')).toHaveTextContent('Chicken, broilers or fryers, breast');

    const nutrientTable = screen.getByTestId('nutrients-table');
    expect(nutrientTable).toBeInTheDocument();
    expect(within(nutrientTable).getByText('Energy')).toBeInTheDocument();
    expect(screen.getByTestId('nutrient-row-1008')).toHaveTextContent('165 kcal');
    expect(within(nutrientTable).getByText('Protein')).toBeInTheDocument();
    expect(screen.getByTestId('nutrient-row-1003')).toHaveTextContent('31.02 g');
  });

  it('18. strictly distinguishes between null nutrient values and 0.00', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('usda-search-input'), 'chicken');
    await user.click(screen.getByTestId('usda-search-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('usda-item-171077')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('usda-item-171077'));

    await waitFor(() => {
      expect(screen.getByTestId('nutrients-table')).toBeInTheDocument();
    });

    // 0.0 Carbohydrate must render as "0 g", NOT "Unavailable"
    expect(screen.getByTestId('nutrient-row-1005')).toHaveTextContent('0 g');

    // null Fiber must render as "Unavailable", NOT "0 g"
    expect(screen.getByTestId('nutrient-row-1079')).toHaveTextContent('Unavailable');
  });

  it('19. displays empirical household portion mappings with gram weights', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('usda-search-input'), 'chicken');
    await user.click(screen.getByTestId('usda-search-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('usda-item-171077')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('usda-item-171077'));

    await waitFor(() => {
      expect(screen.getByTestId('food-portions-list')).toBeInTheDocument();
    });

    expect(screen.getByText(/1 breast, bone and skin removed/i)).toBeInTheDocument();
    expect(screen.getByText('(86g)')).toBeInTheDocument();
    expect(screen.getByText(/1 cup, chopped or diced/i)).toBeInTheDocument();
    expect(screen.getByText('(140g)')).toBeInTheDocument();
  });

  it('20. displays empty results state when no USDA foods match query', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('usda-search-input'), 'nonexistentfood');
    await user.click(screen.getByTestId('usda-search-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('usda-empty-results')).toBeInTheDocument();
    });

    expect(screen.getByTestId('usda-empty-results')).toHaveTextContent(
      /No items in the USDA SR Legacy index matched/i
    );
  });

  it('21. handles search failure and shows retry button', async () => {
    global.fetch = setupMockFetch({ usdaSearchStatus: 500 });
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('usda-search-input'), 'chicken');
    await user.click(screen.getByTestId('usda-search-btn'));

    expect(await screen.findByTestId('usda-search-error')).toBeInTheDocument();
    expect(screen.getByTestId('usda-retry-btn')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group D: Recipe Nutrition Estimator & Decomposition
  // --------------------------------------------------------------------------

  it('22. fetches recipe details and calculates USDA nutritional decomposition', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    const input = screen.getByTestId('estimator-id-input');
    await user.type(input, 'rcp_foodcom_358911');
    await user.click(screen.getByTestId('estimator-submit-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('estimator-result-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('estimator-coverage')).toHaveTextContent('Coverage:100%(3 of 3 mapped)');
    expect(screen.getByTestId('estimator-status-badge')).toHaveTextContent('USDA Estimated (Calculated)');
    expect(screen.getByTestId('est-calories')).toHaveTextContent('370 kcal');
    expect(screen.getByTestId('est-protein')).toHaveTextContent('33 g');
    expect(screen.getByTestId('est-carbs')).toHaveTextContent('1.2 g');
    expect(screen.getByTestId('est-fat')).toHaveTextContent('9 g');
  });

  it('23. warns about unmapped ingredients when coverage is partial', async () => {
    global.fetch = setupMockFetch({ recipeEstimateResponse: mockRecipeEstimatePartial });
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('estimator-id-input'), 'rcp_foodcom_358911');
    await user.click(screen.getByTestId('estimator-submit-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('unmapped-ingredients-list')).toBeInTheDocument();
    });

    expect(screen.getByTestId('estimator-coverage')).toHaveTextContent('Coverage:50%(2 of 4 mapped)');
    expect(screen.getByText('2 pinches exotic herb blend')).toBeInTheDocument();
    expect(screen.getByText('secret spice rub')).toBeInTheDocument();
  });

  it('24. loads sample recipe when quick chip is clicked', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderNutritionPage();

    const sampleChip = screen.getByTestId('sample-chip-foodcom');
    await user.click(sampleChip);

    expect((screen.getByTestId('estimator-id-input') as HTMLInputElement).value).toBe(
      'rcp_foodcom_358911'
    );

    await waitFor(() => {
      expect(screen.getByTestId('estimator-result-card')).toBeInTheDocument();
    });
  });

  // --------------------------------------------------------------------------
  // Group E: Recipe Detail Page On-Demand Integration & Privacy Invariants
  // --------------------------------------------------------------------------

  it('25. displays Calculate USDA Nutrition action on recipe detail page when nutrition is unavailable and calculates on click', async () => {
    global.fetch = setupMockFetch({
      cachedNutritionStatus: 404,
      recipeEstimateResponse: mockRecipeEstimateSuccess,
    });
    const user = userEvent.setup();

    renderNutritionPage('/recipes/rcp_foodcom_358911');

    await waitFor(() => {
      expect(screen.getByTestId('calculate-usda-nutrition-btn')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('calculate-usda-nutrition-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('usda-nutrition-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('nutrition-status-badge')).toHaveTextContent('USDA Estimated (Calculated)');
    expect(screen.getByTestId('nutrition-coverage')).toHaveTextContent('Coverage: 100%');
  });

  it('26. privacy invariant: zero biometric information written to localStorage, sessionStorage or cookies', async () => {
    global.fetch = setupMockFetch({ biometricsResponse: mockMaleBiometricsResponse });
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '32');
    await user.selectOptions(screen.getByTestId('select-sex'), 'male');
    await user.type(screen.getByTestId('input-height'), '182');
    await user.type(screen.getByTestId('input-weight'), '78');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('results-active-card')).toBeInTheDocument();
    });

    // Verify storage remains pristine
    expect(localStorage.getItem('foodflow_biometrics')).toBeNull();
    expect(localStorage.getItem('biometrics')).toBeNull();
    expect(sessionStorage.getItem('foodflow_biometrics')).toBeNull();
    expect(document.cookie).not.toContain('biometrics');
  });

  it('27. guest session invariant: requests to Profile Service do not transmit X-Guest-Session-ID header', async () => {
    const mockFetch = setupMockFetch({ biometricsResponse: mockMaleBiometricsResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderNutritionPage();

    await user.type(screen.getByTestId('input-age'), '30');
    await user.type(screen.getByTestId('input-height'), '180');
    await user.type(screen.getByTestId('input-weight'), '80');

    await user.click(screen.getByTestId('submit-biometrics-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('results-active-card')).toBeInTheDocument();
    });

    const call = mockFetch.mock.calls.find((c) =>
      c[0].toString().includes('/api/v1/biometrics/calculate')
    );
    expect(call).toBeDefined();
    const headers = (call![1]?.headers as Record<string, string>) || {};
    expect(headers['X-Guest-Session-ID']).toBeUndefined();
  });
});
