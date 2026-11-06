import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { routes } from '../router';
import { ThemeProvider } from '../theme/ThemeContext';
import { RecipeDetail } from '../api/types/recipe';
import { CachedRecipeNutrition } from '../api/types/profile';

const mockFoodComRecipe: RecipeDetail = {
  id: 'rcp_foodcom_5421',
  source_dataset: 'food_com',
  source_id: '5421',
  title: 'Classic Rosemary Garlic Roasted Chicken',
  description: 'Succulent whole roasted chicken infused with fresh rosemary and garlic.',
  prep_time_minutes: 15,
  cook_time_minutes: 60,
  total_time_minutes: 75,
  servings: 4,
  cuisine: 'Mediterranean',
  source_url: 'https://www.food.com/recipe/rosemary-chicken-5421',
  submitted_date: '2002-04-18',
  created_at: '2026-11-03T07:00:00Z',
  rating_average: 4.75,
  rating_count: 28,
  ingredients: [
    {
      position: 1,
      raw_text: '3 lbs whole chicken',
      canonical_ingredient_id: 101,
      canonical_name: 'whole chicken',
      quantity: 3,
      unit: 'lbs',
    },
    {
      position: 2,
      raw_text: '4 cloves garlic, minced',
      canonical_ingredient_id: 10,
      canonical_name: 'garlic clove',
      quantity: 4,
      unit: 'cloves',
    },
    {
      position: 3,
      raw_text: '2 tbsp fresh rosemary, chopped',
      canonical_ingredient_id: null,
      canonical_name: null,
      quantity: 2,
      unit: 'tbsp',
    },
    {
      position: 4,
      raw_text: 'Salt and black pepper to taste',
      canonical_ingredient_id: null,
      canonical_name: null,
      quantity: null,
      unit: null,
    },
  ],
  instructions: [
    {
      step_number: 1,
      instruction: 'Preheat oven to 375 degrees F (190 degrees C). Lightly oil a roasting pan.',
    },
    {
      step_number: 2,
      instruction: 'Rinse chicken inside and out with cold water. Pat thoroughly dry with paper towels.',
    },
    {
      step_number: 3,
      instruction: 'Rub garlic and chopped rosemary under and over the skin. Season generously with salt and pepper.',
    },
    {
      step_number: 4,
      instruction: 'Roast in preheated oven for 60 to 75 minutes until juices run clear.',
    },
  ],
  tags: ['dinner', 'chicken', 'poultry', 'roast', 'gluten-free'],
  raw_nutrition: {
    raw_calories: 385.4,
    raw_total_fat_pdv: 22.0,
    raw_sugar_pdv: 2.0,
    raw_sodium_pdv: 18.0,
    raw_protein_pdv: 54.0,
    raw_saturated_fat_pdv: 17.0,
    raw_carbohydrates_pdv: 1.0,
  },
};

const mockRecipeNLGRecipe: RecipeDetail = {
  id: 'rcp_nlg_108294',
  source_dataset: 'recipenlg',
  source_id: '108294',
  title: 'Rustic Herb Flatbread',
  description: null,
  prep_time_minutes: null,
  cook_time_minutes: null,
  total_time_minutes: null,
  servings: null,
  cuisine: null,
  source_url: null,
  submitted_date: null,
  created_at: '2026-11-03T07:00:00Z',
  rating_average: null,
  rating_count: 0,
  ingredients: [
    {
      position: 1,
      raw_text: '2 cups all-purpose flour',
      canonical_ingredient_id: 201,
      canonical_name: 'all-purpose flour',
      quantity: 2,
      unit: 'cups',
    },
    {
      position: 2,
      raw_text: '1 cup warm water',
      canonical_ingredient_id: null,
      canonical_name: null,
      quantity: 1,
      unit: 'cup',
    },
  ],
  instructions: [
    {
      step_number: 1,
      instruction: 'Mix flour and warm water in a large bowl.',
    },
    {
      step_number: 2,
      instruction: 'Knead on floured board until elastic.',
    },
  ],
  tags: ['bread', 'baking'],
  raw_nutrition: null,
};

const mockNoInstructionsRecipe: RecipeDetail = {
  ...mockRecipeNLGRecipe,
  id: 'rcp_nlg_999999',
  title: 'Bare Ingredient List Without Directions',
  instructions: [],
};

const mockCalculatedNutrition: CachedRecipeNutrition = {
  recipe_id: 'rcp_foodcom_5421',
  status: 'calculated',
  calories_kcal: 420.5,
  protein_g: 38.2,
  carbohydrates_g: 4.1,
  total_fat_g: 28.3,
  saturated_fat_g: 7.9,
  fiber_g: 0.8,
  sugar_g: 0.2,
  sodium_mg: 310.0,
  ingredient_coverage_pct: 100.0,
  mapped_ingredient_count: 4,
  total_ingredient_count: 4,
  servings: 4,
  provenance_note: 'Aggregated from USDA SR Legacy nutrient items (101, 10).',
  calculated_at: '2026-11-03T07:00:00Z',
  updated_at: '2026-11-03T07:00:00Z',
};

const mockPartialNutrition: CachedRecipeNutrition = {
  recipe_id: 'rcp_foodcom_5421',
  status: 'partial',
  calories_kcal: 210.0,
  protein_g: 15.0,
  carbohydrates_g: 22.0,
  total_fat_g: 6.0,
  saturated_fat_g: null,
  fiber_g: null,
  sugar_g: null,
  sodium_mg: 150.0,
  ingredient_coverage_pct: 50.0,
  mapped_ingredient_count: 2,
  total_ingredient_count: 4,
  servings: 4,
  provenance_note: 'Partial USDA coverage (50% mapped).',
  calculated_at: '2026-11-03T07:00:00Z',
  updated_at: '2026-11-03T07:00:00Z',
};

const mockUncalculatedNutrition: CachedRecipeNutrition = {
  recipe_id: 'rcp_nlg_108294',
  status: 'uncalculated',
  calories_kcal: null,
  protein_g: null,
  carbohydrates_g: null,
  total_fat_g: null,
  saturated_fat_g: null,
  fiber_g: null,
  sugar_g: null,
  sodium_mg: null,
  ingredient_coverage_pct: 15.0,
  mapped_ingredient_count: 1,
  total_ingredient_count: 6,
  servings: null,
  provenance_note: 'Ingredient coverage insufficient for estimation.',
  calculated_at: '2026-11-03T07:00:00Z',
  updated_at: '2026-11-03T07:00:00Z',
};

function setupMockFetch(options: {
  recipe?: RecipeDetail | null;
  nutrition?: CachedRecipeNutrition | null;
  recipeStatus?: number;
  nutritionStatus?: number;
}) {
  const {
    recipe = mockFoodComRecipe,
    nutrition = mockCalculatedNutrition,
    recipeStatus = 200,
    nutritionStatus = 200,
  } = options;

  return vi.fn().mockImplementation((url: string | URL) => {
    const urlStr = url.toString();

    // 1. Recipe Service detail endpoint
    if (urlStr.includes('/api/v1/recipes/')) {
      if (recipeStatus === 200 && recipe) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => recipe,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: recipeStatus,
          statusText: recipeStatus === 404 ? 'Not Found' : 'Internal Server Error',
          json: async () => ({
            error: {
              code: recipeStatus === 404 ? 'RECIPE_NOT_FOUND' : 'INTERNAL_ERROR',
              message: recipeStatus === 404 ? 'Recipe was not found' : 'Database query failed',
            },
          }),
        });
      }
    }

    // 2. Profile Service nutrition endpoint
    if (urlStr.includes('/api/v1/nutrition/recipes/')) {
      if (nutritionStatus === 200 && nutrition) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => nutrition,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: nutritionStatus,
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

    return Promise.reject(new Error(`Unhandled mock fetch URL: ${urlStr}`));
  });
}

function renderRecipeDetail(recipeId: string = 'rcp_foodcom_5421') {
  const router = createMemoryRouter(routes, {
    initialEntries: [`/recipes/${recipeId}`],
  });

  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

describe('Recipe Details, Ingredients, Instructions & Cooking Mode (Step 05.3)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    localStorage.clear();
  });

  // ==========================================
  // Section A: Recipe Detail Loading & Core View
  // ==========================================

  it('1. successful recipe loading', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    // Initially shows loading state
    expect(screen.getByTestId('recipe-loading')).toBeInTheDocument();

    // Resolves and displays full recipe detail page
    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('recipe-loading')).not.toBeInTheDocument();
  });

  it('2. correct title and metadata rendering', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-title')).toHaveTextContent(
        'Classic Rosemary Garlic Roasted Chicken'
      );
    });

    // Check dataset badge, cuisine, servings, description
    expect(screen.getByTestId('recipe-dataset-badge')).toHaveTextContent('Food.com');
    expect(screen.getByTestId('recipe-cuisine-badge')).toHaveTextContent('Mediterranean');
    expect(screen.getByTestId('recipe-servings-badge')).toHaveTextContent('Serves 4');
    expect(screen.getByTestId('recipe-detail-description')).toHaveTextContent(
      'Succulent whole roasted chicken'
    );

    // Tags list
    const tagsList = screen.getByTestId('recipe-tags-list');
    expect(within(tagsList).getByText('#chicken')).toBeInTheDocument();
    expect(within(tagsList).getByText('#roast')).toBeInTheDocument();
  });

  it('3. ordered ingredient rendering', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-ingredients-section')).toBeInTheDocument();
    });

    const items = screen.getAllByRole('listitem');
    expect(items.length).toBeGreaterThanOrEqual(4);
    // First 4 items in ingredients list
    expect(screen.getByTestId('ingredient-item-1')).toHaveTextContent('3 lbs whole chicken');
    expect(screen.getByTestId('ingredient-item-2')).toHaveTextContent('4 cloves garlic, minced');
    expect(screen.getByTestId('ingredient-item-3')).toHaveTextContent('2 tbsp fresh rosemary');
    expect(screen.getByTestId('ingredient-item-4')).toHaveTextContent('Salt and black pepper to taste');

    // Canonical badge rendering
    expect(screen.getByTestId('canonical-badge-1')).toHaveTextContent('Canonical: whole chicken');
    expect(screen.getByTestId('canonical-badge-2')).toHaveTextContent('Canonical: garlic clove');
    expect(screen.queryByTestId('canonical-badge-3')).not.toBeInTheDocument();
  });

  it('4. ingredient quantities and units', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('ingredient-item-1')).toBeInTheDocument();
    });

    const item1 = screen.getByTestId('ingredient-item-1');
    expect(item1).toHaveTextContent('3 lbs');

    const item2 = screen.getByTestId('ingredient-item-2');
    expect(item2).toHaveTextContent('4 cloves');
  });

  it('5. missing quantity/unit handling', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('ingredient-item-4')).toBeInTheDocument();
    });

    // Item 4 has null quantity and null unit; should not display 0 or null
    const item4 = screen.getByTestId('ingredient-item-4');
    expect(item4).toHaveTextContent('Salt and black pepper to taste');
    expect(item4).not.toHaveTextContent('0');
    expect(item4).not.toHaveTextContent('null');
  });

  it('6. ordered instruction rendering', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-instructions-section')).toBeInTheDocument();
    });

    expect(screen.getByTestId('instruction-step-1')).toHaveTextContent(
      'Preheat oven to 375 degrees F'
    );
    expect(screen.getByTestId('instruction-step-2')).toHaveTextContent(
      'Rinse chicken inside and out'
    );
    expect(screen.getByTestId('instruction-step-3')).toHaveTextContent(
      'Rub garlic and chopped rosemary'
    );
    expect(screen.getByTestId('instruction-step-4')).toHaveTextContent(
      'Roast in preheated oven for 60 to 75 minutes'
    );
  });

  it('7. missing instructions handling', async () => {
    global.fetch = setupMockFetch({ recipe: mockNoInstructionsRecipe, nutritionStatus: 404 });
    renderRecipeDetail('rcp_nlg_999999');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();
    });

    expect(screen.getByTestId('empty-instructions')).toBeInTheDocument();
    expect(screen.getByText('No cooking instructions available for this recipe.')).toBeInTheDocument();
    expect(screen.queryByTestId('enter-cooking-mode-btn')).not.toBeInTheDocument();
  });

  it('8. missing rating and time handling', async () => {
    global.fetch = setupMockFetch({ recipe: mockRecipeNLGRecipe, nutritionStatus: 404 });
    renderRecipeDetail('rcp_nlg_108294');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();
    });

    // RecipeNLG has null ratings and times -> must show honest 'Rating unavailable' and 'Time unavailable'
    expect(screen.getByTestId('recipe-rating-pill')).toHaveTextContent('Rating unavailable');
    expect(screen.getByTestId('recipe-rating-pill')).not.toHaveTextContent('0');

    expect(screen.getByTestId('recipe-time-pill')).toHaveTextContent('Time unavailable');
    expect(screen.getByTestId('recipe-time-pill')).not.toHaveTextContent('0 mins');
  });

  it('9. recipe not found (404 state)', async () => {
    global.fetch = setupMockFetch({ recipeStatus: 404, recipe: null });
    renderRecipeDetail('rcp_foodcom_nonexistent');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-not-found')).toBeInTheDocument();
    });

    expect(screen.getByText('Recipe Not Found')).toBeInTheDocument();
    expect(screen.getByTestId('back-to-recipes-btn')).toHaveAttribute('href', '/recipes');
  });

  it('10. recipe API failure and retry', async () => {
    let callCount = 0;
    global.fetch = vi.fn().mockImplementation((url: string | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes('/api/v1/recipes/')) {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error',
            json: async () => ({ error: { message: 'Database connection failed' } }),
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockFoodComRecipe,
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockCalculatedNutrition,
      });
    });

    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-error')).toBeInTheDocument();
    });

    // Click retry
    const retryBtn = screen.getByTestId('recipe-retry-btn');
    await user.click(retryBtn);

    // Resolves and displays page
    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();
    });
  });

  it('11. navigation back to discovery', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();
    });

    const bottomBackLink = screen.getByTestId('bottom-back-to-recipes');
    expect(bottomBackLink).toHaveAttribute('href', '/recipes');
  });

  // ==========================================
  // Section B: Nutrition Information
  // ==========================================

  it('12. calculated nutrition display', async () => {
    global.fetch = setupMockFetch({
      recipe: mockFoodComRecipe,
      nutrition: mockCalculatedNutrition,
    });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('usda-nutrition-card')).toBeInTheDocument();
    });

    // Check status badge and coverage
    expect(screen.getByTestId('nutrition-status-badge')).toHaveTextContent(
      'USDA Estimated (Calculated)'
    );
    expect(screen.getByTestId('nutrition-coverage')).toHaveTextContent('Coverage: 100%');

    // Nutrient values
    expect(screen.getByTestId('metric-calories')).toHaveTextContent('421 kcal');
    expect(screen.getByTestId('metric-protein')).toHaveTextContent('38.2 g');
    expect(screen.getByTestId('metric-carbs')).toHaveTextContent('4.1 g');
    expect(screen.getByTestId('metric-fat')).toHaveTextContent('28.3 g');
    expect(screen.getByTestId('metric-sat-fat')).toHaveTextContent('7.9 g');
    expect(screen.getByTestId('metric-sodium')).toHaveTextContent('310 mg');

    // Mandatory disclaimer
    expect(screen.getByTestId('clinical-disclaimer')).toHaveTextContent(
      'Nutritional values are mathematical estimates'
    );
  });

  it('13. partial nutrition display', async () => {
    global.fetch = setupMockFetch({
      recipe: mockFoodComRecipe,
      nutrition: mockPartialNutrition,
    });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('usda-nutrition-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('nutrition-status-badge')).toHaveTextContent('Partial Coverage');
    expect(screen.getByTestId('nutrition-coverage')).toHaveTextContent('Coverage: 50%');
    expect(screen.getByTestId('metric-calories')).toHaveTextContent('210 kcal');
  });

  it('14. uncalculated nutrition display', async () => {
    global.fetch = setupMockFetch({
      recipe: mockRecipeNLGRecipe,
      nutrition: mockUncalculatedNutrition,
    });
    renderRecipeDetail('rcp_nlg_108294');

    await waitFor(() => {
      expect(screen.getByTestId('usda-nutrition-card')).toBeInTheDocument();
    });

    expect(screen.getByTestId('nutrition-status-badge')).toHaveTextContent('Uncalculated');
    expect(screen.getByTestId('uncalculated-banner')).toHaveTextContent(
      'Ingredient coverage was insufficient'
    );
  });

  it('15. missing nutrient handling (does not default to zero)', async () => {
    global.fetch = setupMockFetch({
      recipe: mockFoodComRecipe,
      nutrition: mockPartialNutrition,
    });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('usda-nutrition-card')).toBeInTheDocument();
    });

    // In mockPartialNutrition, saturated_fat_g and fiber_g are null
    expect(screen.getByTestId('metric-sat-fat')).toHaveTextContent('Unavailable');
    expect(screen.getByTestId('metric-sat-fat')).not.toHaveTextContent('0 g');

    expect(screen.getByTestId('metric-fiber')).toHaveTextContent('Unavailable');
    expect(screen.getByTestId('metric-fiber')).not.toHaveTextContent('0 g');
  });

  it('16. distinction between measured and estimated nutrition', async () => {
    global.fetch = setupMockFetch({
      recipe: mockFoodComRecipe,
      nutrition: mockCalculatedNutrition,
    });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('usda-nutrition-card')).toBeInTheDocument();
      expect(screen.getByTestId('raw-nutrition-card')).toBeInTheDocument();
    });

    // USDA Estimation card
    const usdaCard = screen.getByTestId('usda-nutrition-card');
    expect(within(usdaCard).getByText('USDA SR Legacy Estimation')).toBeInTheDocument();
    expect(within(usdaCard).getByTestId('metric-calories')).toHaveTextContent('421 kcal');

    // Food.com raw reported %DV card
    const rawCard = screen.getByTestId('raw-nutrition-card');
    expect(within(rawCard).getByText('Source Dataset Reported Metrics')).toBeInTheDocument();
    expect(within(rawCard).getByTestId('raw-calories')).toHaveTextContent('385.4 kcal');
    expect(within(rawCard).getByTestId('raw-protein')).toHaveTextContent('54% DV');
    expect(within(rawCard).getByTestId('raw-fat')).toHaveTextContent('22% DV');
  });

  // ==========================================
  // Section C: Cooking Mode & Persistence
  // ==========================================

  it('17. entering cooking mode', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('enter-cooking-mode-btn')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('enter-cooking-mode-btn'));

    expect(screen.getByTestId('cooking-mode')).toBeInTheDocument();
  });

  it('18. first instruction display in cooking mode', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('enter-cooking-mode-btn')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));

    expect(screen.getByTestId('step-counter')).toHaveTextContent('Step 1 of 4');
    expect(screen.getByTestId('active-instruction-text')).toHaveTextContent(
      'Preheat oven to 375 degrees F (190 degrees C). Lightly oil a roasting pan.'
    );
  });

  it('19. next and previous behavior', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('enter-cooking-mode-btn')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));

    // Step 1 -> Click Next -> Step 2
    const nextBtn = screen.getByTestId('cooking-next-btn');
    await user.click(nextBtn);

    expect(screen.getByTestId('step-counter')).toHaveTextContent('Step 2 of 4');
    expect(screen.getByTestId('active-instruction-text')).toHaveTextContent(
      'Rinse chicken inside and out with cold water.'
    );

    // Step 2 -> Click Prev -> Step 1
    const prevBtn = screen.getByTestId('cooking-prev-btn');
    await user.click(prevBtn);

    expect(screen.getByTestId('step-counter')).toHaveTextContent('Step 1 of 4');
  });

  it('20. first/last step boundaries', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('enter-cooking-mode-btn')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));

    // On Step 1: Previous is disabled
    expect(screen.getByTestId('cooking-prev-btn')).toBeDisabled();
    expect(screen.getByTestId('cooking-next-btn')).not.toBeDisabled();

    // Advance to Step 4 (last step)
    const nextBtn = screen.getByTestId('cooking-next-btn');
    await user.click(nextBtn); // Step 2
    await user.click(nextBtn); // Step 3
    await user.click(nextBtn); // Step 4

    expect(screen.getByTestId('step-counter')).toHaveTextContent('Step 4 of 4');
    expect(screen.getByTestId('cooking-next-btn')).toBeDisabled();
    expect(screen.getByTestId('cooking-prev-btn')).not.toBeDisabled();
  });

  it('21. progress indicator updates with steps', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('enter-cooking-mode-btn')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));

    const progressBar = screen.getByTestId('cooking-progress-bar');
    expect(progressBar).toHaveAttribute('aria-valuenow', '1');

    const nextBtn = screen.getByTestId('cooking-next-btn');
    await user.click(nextBtn);

    expect(progressBar).toHaveAttribute('aria-valuenow', '2');
    expect(screen.getByTestId('step-counter')).toHaveTextContent('50% Complete');
  });

  it('22. exiting cooking mode returns to recipe details preserving step', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('enter-cooking-mode-btn')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));

    // Advance to step 3
    const nextBtn = screen.getByTestId('cooking-next-btn');
    await user.click(nextBtn); // step 2
    await user.click(nextBtn); // step 3

    // Exit
    await user.click(screen.getByTestId('exit-cooking-mode-btn'));

    // Returns to normal recipe detail page
    expect(screen.queryByTestId('cooking-mode')).not.toBeInTheDocument();
    expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();

    // Re-entering cooking mode resumes at step 3
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));
    expect(screen.getByTestId('step-counter')).toHaveTextContent('Step 3 of 4');
  });

  it('23. ingredient checklist interactions', async () => {
    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    const user = userEvent.setup();
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-ingredients-section')).toBeInTheDocument();
    });

    const checkbox1 = screen.getByTestId('ingredient-checkbox-1');
    expect(checkbox1).not.toBeChecked();

    // Toggle check
    await user.click(checkbox1);
    expect(checkbox1).toBeChecked();
    expect(screen.getByTestId('checklist-progress')).toHaveTextContent('1 of 4 prepped');

    // Toggle off
    await user.click(checkbox1);
    expect(checkbox1).not.toBeChecked();
  });

  it('24. recipe-specific local persistence', async () => {
    // Pre-populate localStorage for this recipe
    const savedState = {
      currentStep: 2, // Step 3
      checkedPositions: [1, 2],
    };
    localStorage.setItem('foodflow_cooking_rcp_foodcom_5421', JSON.stringify(savedState));

    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();
    });

    // Check prepped checklist counter rehydrated
    expect(screen.getByTestId('checklist-progress')).toHaveTextContent('2 of 4 prepped');
    expect(screen.getByTestId('ingredient-checkbox-1')).toBeChecked();
    expect(screen.getByTestId('ingredient-checkbox-2')).toBeChecked();

    // Open cooking mode -> starts on saved Step 3
    const user = userEvent.setup();
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));
    expect(screen.getByTestId('step-counter')).toHaveTextContent('Step 3 of 4');
  });

  it('25. invalid persisted state handling', async () => {
    // Store corrupted JSON and out-of-bounds index
    localStorage.setItem(
      'foodflow_cooking_rcp_foodcom_5421',
      '{ invalid_json: true, currentStep: 9999 }'
    );

    global.fetch = setupMockFetch({ recipe: mockFoodComRecipe });
    renderRecipeDetail('rcp_foodcom_5421');

    // Does not throw an error and renders gracefully with default step 0
    await waitFor(() => {
      expect(screen.getByTestId('recipe-detail-page')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('enter-cooking-mode-btn'));
    expect(screen.getByTestId('step-counter')).toHaveTextContent('Step 1 of 4');
  });
});
