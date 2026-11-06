import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { profileClient, ProfileServiceClient } from '../api/profileClient';
import { recipeClient, RecipeServiceClient } from '../api/recipeClient';
import { plannerClient, PlannerServiceClient } from '../api/plannerClient';

describe('Microservice Typed API Clients & Header Isolation', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  describe('Profile & Nutrition Service Client (Port 8001)', () => {
    it('initializes with default base URL targeting port 8001', () => {
      expect(profileClient.getBaseUrl()).toBe('http://localhost:8001');
    });

    it('allows custom base URL override', () => {
      const client = new ProfileServiceClient('https://profile.foodflow.internal:8443/');
      expect(client.getBaseUrl()).toBe('https://profile.foodflow.internal:8443');
    });

    it('invokes calculateBiometrics with POST and never sends X-Guest-Session-ID', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          bmi: 24.15,
          bmi_category: 'normal_weight',
          bmr_kcal: 1802.5,
          tdee_kcal: 2793.88,
          target_calories_kcal: 2794,
        }),
      });
      global.fetch = mockFetch;

      const payload = {
        age_years: 28,
        sex_for_equation: 'male' as const,
        height_cm: 182.0,
        weight_kg: 80.0,
        activity_level: 'moderately_active' as const,
      };

      const result = await profileClient.calculateBiometrics(payload);
      expect(result.bmi).toBe(24.15);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('http://localhost:8001/api/v1/biometrics/calculate');
      expect(init.method).toBe('POST');
      expect(init.headers['X-Request-ID']).toBeTruthy();
      expect(init.headers['X-Guest-Session-ID']).toBeUndefined();
    });

    it('invokes searchFoods with query params and never sends X-Guest-Session-ID', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ data: [], pagination: { total: 0, limit: 10, offset: 0 } }),
      });
      global.fetch = mockFetch;

      await profileClient.searchFoods('rolled oats', 10, 1);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain('http://localhost:8001/api/v1/nutrition/foods/search');
      expect(url).toContain('q=rolled+oats');
      expect(init.headers['X-Guest-Session-ID']).toBeUndefined();
    });
  });

  describe('Recipe & Ingredient Service Client (Port 8002)', () => {
    it('initializes with default base URL targeting port 8002', () => {
      expect(recipeClient.getBaseUrl()).toBe('http://localhost:8002');
      const customClient = new RecipeServiceClient('https://custom-recipe:9002');
      expect(customClient.getBaseUrl()).toBe('https://custom-recipe:9002');
    });

    it('invokes searchRecipes with params and never sends X-Guest-Session-ID', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          data: [],
          pagination: { page: 1, limit: 24, total_items: 0, total_pages: 0 },
        }),
      });
      global.fetch = mockFetch;

      await recipeClient.searchRecipes({
        q: 'rosemary chicken',
        cuisine: 'Italian',
        diet: 'gluten-free',
        max_time: 60,
        sort: 'rating',
        page: 2,
        limit: 24,
      });

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toContain('http://localhost:8002/api/v1/recipes/search');
      expect(url).toContain('q=rosemary+chicken');
      expect(url).toContain('cuisine=Italian');
      expect(url).toContain('diet=gluten-free');
      expect(url).toContain('max_time=60');
      expect(url).toContain('sort=rating');
      expect(url).toContain('page=2');
      expect(url).toContain('limit=24');
      expect(init.headers['X-Request-ID']).toBeTruthy();
      expect(init.headers['X-Guest-Session-ID']).toBeUndefined();
    });

    it('invokes normalizeIngredients with POST and never sends X-Guest-Session-ID', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          results: [{ raw_input: 'garlic cloves', matched: true, canonical_id: 10 }],
        }),
      });
      global.fetch = mockFetch;

      const res = await recipeClient.normalizeIngredients(['garlic cloves']);
      expect(res.results).toHaveLength(1);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('http://localhost:8002/api/v1/ingredients/normalize');
      expect(init.method).toBe('POST');
      expect(init.headers['X-Guest-Session-ID']).toBeUndefined();
    });

    it('invokes getIngredientSuggestions with query params and never sends X-Guest-Session-ID', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => [
          { id: 101, name: 'chicken breast', category: 'poultry', is_pantry_staple: false },
        ],
      });
      global.fetch = mockFetch;

      const res = await recipeClient.getIngredientSuggestions('chick', 10);
      expect(res).toHaveLength(1);
      expect(res[0].id).toBe(101);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('http://localhost:8002/api/v1/ingredients/suggestions?q=chick&limit=10');
      expect(init.method).toBe('GET');
      expect(init.headers['X-Guest-Session-ID']).toBeUndefined();
    });
  });

  describe('Recommendation & Meal Planner Service Client (Port 8003)', () => {
    const testSessionId = 'e4eaaaf2-d142-4f01-9e73-b3c990b79f82';

    it('initializes with default base URL targeting port 8003', () => {
      expect(plannerClient.getBaseUrl()).toBe('http://localhost:8003');
      const customClient = new PlannerServiceClient('https://custom-planner:9003');
      expect(customClient.getBaseUrl()).toBe('https://custom-planner:9003');
    });

    it('invokes createGuestSession without requiring an initial session header', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          session_id: testSessionId,
          created_at: '2026-11-03T07:00:00Z',
          expires_at: '2026-12-03T07:00:00Z',
          last_active_at: '2026-11-03T07:00:00Z',
        }),
      });
      global.fetch = mockFetch;

      const session = await plannerClient.createGuestSession();
      expect(session.session_id).toBe(testSessionId);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('http://localhost:8003/api/v1/guest-sessions');
      expect(init.headers['X-Guest-Session-ID']).toBeUndefined();
    });

    it('invokes getGuestSession with path parameter and touches session', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          session_id: testSessionId,
          created_at: '2026-11-03T07:00:00Z',
          expires_at: '2026-12-03T07:00:00Z',
          last_active_at: '2026-11-03T07:15:00Z',
        }),
      });
      global.fetch = mockFetch;

      const session = await plannerClient.getGuestSession(testSessionId);
      expect(session.session_id).toBe(testSessionId);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe(`http://localhost:8003/api/v1/guest-sessions/${testSessionId}`);
      expect(init.method).toBe('GET');
      expect(init.headers['X-Guest-Session-ID']).toBeUndefined();
    });

    it('strictly attaches X-Guest-Session-ID when calling getPantry', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], total_count: 0 }),
      });
      global.fetch = mockFetch;

      await plannerClient.getPantry(testSessionId);

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('http://localhost:8003/api/v1/pantry');
      expect(init.headers['X-Guest-Session-ID']).toBe(testSessionId);
    });

    it('strictly attaches X-Guest-Session-ID when calling updatePantry', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ items: [], total_count: 0 }),
      });
      global.fetch = mockFetch;

      await plannerClient.updatePantry(
        [{ raw_name: 'chicken thighs', canonical_ingredient_id: 101 }],
        testSessionId
      );

      const [url, init] = mockFetch.mock.calls[0];
      expect(url).toBe('http://localhost:8003/api/v1/pantry');
      expect(init.method).toBe('PUT');
      expect(init.headers['X-Guest-Session-ID']).toBe(testSessionId);
    });

    it('attaches X-Guest-Session-ID to saveMealPlan, getMealPlan, and deleteMealPlan', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: 'plan-123', name: 'Weekly Plan', days: 7, slots: [] }),
      });
      global.fetch = mockFetch;

      // Save Plan
      await plannerClient.saveMealPlan(
        { name: 'Weekly Plan', days: 7, slots: [] },
        testSessionId
      );
      expect(mockFetch.mock.calls[0][0]).toBe('http://localhost:8003/api/v1/meal-plans');
      expect(mockFetch.mock.calls[0][1].headers['X-Guest-Session-ID']).toBe(testSessionId);

      // Get Plan
      await plannerClient.getMealPlan('plan-123', testSessionId);
      expect(mockFetch.mock.calls[1][0]).toBe('http://localhost:8003/api/v1/meal-plans/plan-123');
      expect(mockFetch.mock.calls[1][1].headers['X-Guest-Session-ID']).toBe(testSessionId);

      // Delete Plan (204)
      mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });
      await plannerClient.deleteMealPlan('plan-123', testSessionId);
      expect(mockFetch.mock.calls[2][0]).toBe('http://localhost:8003/api/v1/meal-plans/plan-123');
      expect(mockFetch.mock.calls[2][1].headers['X-Guest-Session-ID']).toBe(testSessionId);
    });

    it('attaches X-Guest-Session-ID to getShoppingList, updateCookingProgress, and updateShoppingListItem', async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ plan_id: 'plan-123', categories: [], total_items: 0 }),
      });
      global.fetch = mockFetch;

      // Get shopping list
      await plannerClient.getShoppingList('plan-123', testSessionId);
      const [url1, init1] = mockFetch.mock.calls[0];
      expect(url1).toBe('http://localhost:8003/api/v1/meal-plans/plan-123/shopping-list');
      expect(init1.headers['X-Guest-Session-ID']).toBe(testSessionId);

      // Update cooking progress
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ updated_count: 1, plan_id: 'plan-123' }),
      });
      await plannerClient.updateCookingProgress(
        'plan-123',
        [{ slot_id: 101, cooking_status: 'cooked' }],
        testSessionId
      );
      const [url2, init2] = mockFetch.mock.calls[1];
      expect(url2).toBe('http://localhost:8003/api/v1/meal-plans/plan-123/progress');
      expect(init2.headers['X-Guest-Session-ID']).toBe(testSessionId);

      // Update shopping item
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ id: 12, ingredient_name: 'rosemary', checked: true }),
      });
      await plannerClient.updateShoppingListItem('plan-123', 12, true, testSessionId);
      const [url3, init3] = mockFetch.mock.calls[2];
      expect(url3).toBe('http://localhost:8003/api/v1/meal-plans/plan-123/shopping-list/items/12');
      expect(init3.headers['X-Guest-Session-ID']).toBe(testSessionId);
    });
  });
});
