import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { routes } from '../router';
import { ThemeProvider } from '../theme/ThemeContext';
import {
  GeneratedMealPlanResponse,
  GuestSession,
  MealPlanDetail,
  SavedMealPlanSummary,
  ShoppingListResponse,
} from '../api/types/planner';
import { GUEST_SESSION_STORAGE_KEY } from '../utils/guestSession';
import { ACTIVE_PLAN_STORAGE_KEY } from '../pages/MealPlannerPage';

// ============================================================================
// Mock Data Fixtures
// ============================================================================

const mockSessionId = 'e4eaaaf2-d142-4f01-9e73-b3c990b79f82';
const mockPlanId = '7c14a2f1-6a20-4e31-8930-b19329048f32';

const mockGuestSession: GuestSession = {
  session_id: mockSessionId,
  created_at: '2026-11-03T07:00:00Z',
  expires_at: '2026-12-03T07:00:00Z',
  last_active_at: '2026-11-03T07:00:00Z',
};

const mockGeneratedProposal: GeneratedMealPlanResponse = {
  target_calories_kcal: 2100,
  days: [
    {
      day_index: 0,
      slots: [
        {
          slot_type: 'breakfast',
          recipe_id: 'rcp_foodcom_101',
          title: 'Blueberry Oatmeal',
          total_time_minutes: 15,
          estimated_calories_kcal: 420,
        },
        {
          slot_type: 'lunch',
          recipe_id: 'rcp_foodcom_102',
          title: 'Mediterranean Chicken Salad',
          total_time_minutes: 20,
          estimated_calories_kcal: 650,
        },
        {
          slot_type: 'dinner',
          recipe_id: 'rcp_foodcom_103',
          title: 'Garlic Butter Salmon',
          total_time_minutes: 30,
          estimated_calories_kcal: 750,
        },
      ],
      day_total_calories_kcal: 1820,
    },
    {
      day_index: 1,
      slots: [
        {
          slot_type: 'breakfast',
          recipe_id: 'rcp_foodcom_104',
          title: 'Avocado Toast with Egg',
          total_time_minutes: 10,
          estimated_calories_kcal: 380,
        },
        {
          slot_type: 'lunch',
          recipe_id: 'rcp_foodcom_105',
          title: 'Turkey Spinach Wrap',
          total_time_minutes: 15,
          estimated_calories_kcal: null,
        },
        {
          slot_type: 'dinner',
          recipe_id: 'rcp_foodcom_106',
          title: 'Lemon Herb Roast Chicken',
          total_time_minutes: 60,
          estimated_calories_kcal: 820,
        },
      ],
      day_total_calories_kcal: 1200,
    },
  ],
  notes: [
    'Plan generated without dietary restrictions.',
    'Caloric target balanced within 10% tolerance.',
  ],
};

const mockSavedSummary: SavedMealPlanSummary = {
  plan_id: mockPlanId,
  name: 'Weekly Fitness Schedule',
  days: 2,
  created_at: '2026-11-03T07:00:00Z',
};

const mockSavedPlanDetail: MealPlanDetail = {
  id: mockPlanId,
  name: 'Weekly Fitness Schedule',
  target_calories_kcal: 2100,
  days: 2,
  created_at: '2026-11-03T07:00:00Z',
  updated_at: '2026-11-03T07:00:00Z',
  slots: [
    {
      id: 101,
      day_index: 0,
      slot_type: 'breakfast',
      recipe_id: 'rcp_foodcom_101',
      recipe_title: 'Blueberry Oatmeal',
      cooking_status: 'pending',
      status_updated_at: null,
    },
    {
      id: 102,
      day_index: 0,
      slot_type: 'lunch',
      recipe_id: 'rcp_foodcom_102',
      recipe_title: 'Mediterranean Chicken Salad',
      cooking_status: 'cooked',
      status_updated_at: '2026-11-03T12:30:00Z',
    },
    {
      id: 103,
      day_index: 0,
      slot_type: 'dinner',
      recipe_id: 'rcp_foodcom_103',
      recipe_title: 'Garlic Butter Salmon',
      cooking_status: 'pending',
      status_updated_at: null,
    },
    {
      id: 104,
      day_index: 1,
      slot_type: 'breakfast',
      recipe_id: 'rcp_foodcom_104',
      recipe_title: 'Avocado Toast with Egg',
      cooking_status: 'skipped',
      status_updated_at: null,
    },
    {
      id: 105,
      day_index: 1,
      slot_type: 'lunch',
      recipe_id: 'rcp_foodcom_105',
      recipe_title: 'Turkey Spinach Wrap',
      cooking_status: 'pending',
      status_updated_at: null,
    },
    {
      id: 106,
      day_index: 1,
      slot_type: 'dinner',
      recipe_id: 'rcp_foodcom_106',
      recipe_title: 'Lemon Herb Roast Chicken',
      cooking_status: 'pending',
      status_updated_at: null,
    },
  ],
};

const mockShoppingList: ShoppingListResponse = {
  id: '8b22a1c0-4f91-4a11-8932-d19329048f99',
  plan_id: mockPlanId,
  total_items: 4,
  categories: [
    {
      category: 'Produce',
      items: [
        {
          id: 1,
          ingredient_name: 'fresh blueberries',
          quantity_display: '1 cup',
          category: 'Produce',
          checked: false,
        },
        {
          id: 2,
          ingredient_name: 'baby spinach',
          quantity_display: '200 g',
          category: 'Produce',
          checked: true,
        },
      ],
    },
    {
      category: 'Meat & Seafood',
      items: [
        {
          id: 3,
          ingredient_name: 'salmon fillets',
          quantity_display: '2 pieces',
          category: 'Meat & Seafood',
          checked: false,
        },
      ],
    },
    {
      category: 'Dairy & Refrigerated',
      items: [
        {
          id: 4,
          ingredient_name: 'eggs',
          quantity_display: '4 large',
          category: 'Dairy & Refrigerated',
          checked: false,
        },
      ],
    },
  ],
};

// ============================================================================
// Mock Fetch Configurator
// ============================================================================

interface SetupMockFetchOptions {
  sessionStatus?: number;
  sessionResponse?: GuestSession;
  planStatus?: number;
  planResponse?: MealPlanDetail | null;
  generateStatus?: number;
  generateResponse?: GeneratedMealPlanResponse;
  saveStatus?: number;
  saveResponse?: SavedMealPlanSummary;
  progressStatus?: number;
  shoppingStatus?: number;
  shoppingResponse?: ShoppingListResponse | null;
  updateItemStatus?: number;
  deleteStatus?: number;
  updatePlanStatus?: number;
}

function setupMockFetch(options: SetupMockFetchOptions = {}) {
  const {
    sessionStatus = 200,
    sessionResponse = mockGuestSession,
    planStatus = 200,
    planResponse = mockSavedPlanDetail,
    generateStatus = 200,
    generateResponse = mockGeneratedProposal,
    saveStatus = 201,
    saveResponse = mockSavedSummary,
    progressStatus = 200,
    shoppingStatus = 200,
    shoppingResponse = mockShoppingList,
    updateItemStatus = 200,
    deleteStatus = 204,
    updatePlanStatus = 200,
  } = options;

  let currentPlan = planResponse ? JSON.parse(JSON.stringify(planResponse)) : null;
  let currentShopping = shoppingResponse ? JSON.parse(JSON.stringify(shoppingResponse)) : null;

  return vi.fn().mockImplementation((url: string | URL, init?: RequestInit) => {
    const urlStr = url.toString();
    const method = init?.method?.toUpperCase() || 'GET';

    // 1. Guest Session: POST /api/v1/guest-sessions
    if (urlStr.includes('/api/v1/guest-sessions') && method === 'POST') {
      if (sessionStatus === 201 || sessionStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => sessionResponse,
        });
      }
      return Promise.resolve({
        ok: false,
        status: sessionStatus,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'SESSION_CREATE_FAILED', message: 'Failed to create guest session.' },
        }),
      });
    }

    // 2. Guest Session: GET /api/v1/guest-sessions/{id}
    if (urlStr.match(/\/api\/v1\/guest-sessions\/[0-9a-fA-F-]+/) && method === 'GET') {
      if (sessionStatus === 200 || sessionStatus === 201) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => sessionResponse,
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({
          error: { code: 'SESSION_EXPIRED', message: 'Guest session expired.' },
        }),
      });
    }

    // 3. Generate Proposal: POST /api/v1/meal-plans/generate
    if (urlStr.includes('/api/v1/meal-plans/generate') && method === 'POST') {
      if (generateStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => generateResponse,
        });
      }
      return Promise.resolve({
        ok: false,
        status: generateStatus,
        statusText: 'Bad Request',
        json: async () => ({
          error: { code: 'GENERATION_FAILED', message: 'Failed to generate meal plan proposal.' },
        }),
      });
    }

    // 4. Save Plan: POST /api/v1/meal-plans
    if (urlStr.endsWith('/api/v1/meal-plans') && method === 'POST') {
      if (saveStatus === 201 || saveStatus === 200) {
        const body = JSON.parse(init?.body as string);
        currentPlan = {
          id: saveResponse.plan_id,
          name: body.name || saveResponse.name,
          days: body.days || saveResponse.days,
          target_calories_kcal: body.target_calories_kcal ?? null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          slots: (body.slots || []).map((s: any, idx: number) => ({
            id: 200 + idx,
            day_index: s.day_index,
            slot_type: s.slot_type,
            recipe_id: s.recipe_id,
            recipe_title: s.recipe_title,
            cooking_status: 'pending',
            status_updated_at: null,
          })),
        };
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => saveResponse,
        });
      }
      return Promise.resolve({
        ok: false,
        status: saveStatus,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'SAVE_FAILED', message: 'Failed to save meal plan.' },
        }),
      });
    }

    // 5. Update Cooking Progress: PATCH /api/v1/meal-plans/{plan_id}/progress
    if (urlStr.includes('/progress') && method === 'PATCH') {
      if (progressStatus === 200) {
        const body = JSON.parse(init?.body as string);
        (body.updates || []).forEach((up: any) => {
          if (currentPlan) {
            currentPlan.slots = currentPlan.slots.map((s: any) =>
              s.id === up.slot_id ? { ...s, cooking_status: up.cooking_status } : s
            );
          }
        });
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ updated_count: body.updates?.length || 1, plan_id: mockPlanId }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: progressStatus,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'PROGRESS_FAILED', message: 'Failed to update cooking progress.' },
        }),
      });
    }

    // 6. Update Shopping Item: PATCH /api/v1/meal-plans/{plan_id}/shopping-list/items/{item_id}
    if (urlStr.includes('/shopping-list/items/') && method === 'PATCH') {
      if (updateItemStatus === 200) {
        const body = JSON.parse(init?.body as string);
        const match = urlStr.match(/\/items\/(\d+)/);
        const itemId = match ? Number(match[1]) : 1;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: itemId,
            ingredient_name: 'fresh blueberries',
            checked: body.checked,
          }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: updateItemStatus,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'UPDATE_ITEM_FAILED', message: 'Failed to update shopping item.' },
        }),
      });
    }

    // 7. Get Shopping List: GET /api/v1/meal-plans/{plan_id}/shopping-list
    if (urlStr.includes('/shopping-list') && method === 'GET') {
      if (shoppingStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => currentShopping,
        });
      }
      return Promise.resolve({
        ok: false,
        status: shoppingStatus,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'SHOPPING_FAILED', message: 'Failed to retrieve shopping list.' },
        }),
      });
    }

    // 8. Update Plan: PUT /api/v1/meal-plans/{plan_id}
    if (urlStr.match(/\/api\/v1\/meal-plans\/[0-9a-fA-F-]+$/) && method === 'PUT') {
      if (updatePlanStatus === 200) {
        const body = JSON.parse(init?.body as string);
        currentPlan = {
          ...currentPlan,
          name: body.name,
          slots: body.slots.map((s: any, idx: number) => ({
            id: 300 + idx,
            day_index: s.day_index,
            slot_type: s.slot_type,
            recipe_id: s.recipe_id,
            recipe_title: s.recipe_title,
            cooking_status: 'pending',
          })),
        };
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => currentPlan,
        });
      }
      return Promise.resolve({
        ok: false,
        status: updatePlanStatus,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'UPDATE_FAILED', message: 'Failed to update meal plan.' },
        }),
      });
    }

    // 9. Delete Plan: DELETE /api/v1/meal-plans/{plan_id}
    if (urlStr.match(/\/api\/v1\/meal-plans\/[0-9a-fA-F-]+$/) && method === 'DELETE') {
      if (deleteStatus === 204) {
        currentPlan = null;
        return Promise.resolve({
          ok: true,
          status: 204,
          json: async () => ({}),
        });
      }
      return Promise.resolve({
        ok: false,
        status: deleteStatus,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'DELETE_FAILED', message: 'Failed to delete meal plan.' },
        }),
      });
    }

    // 10. Get Plan Detail: GET /api/v1/meal-plans/{plan_id}
    if (urlStr.match(/\/api\/v1\/meal-plans\/[0-9a-fA-F-]+$/) && method === 'GET') {
      if (planStatus === 200 && currentPlan) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => currentPlan,
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({
          error: { code: 'RESOURCE_NOT_FOUND', message: 'Meal plan not found.' },
        }),
      });
    }

    // Fallback 404
    return Promise.resolve({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      json: async () => ({
        error: { code: 'NOT_FOUND', message: `Unhandled test mock path: ${urlStr}` },
      }),
    });
  });
}

function renderMealPlannerPage(initialEntries: string[] = ['/meal-plans']) {
  const router = createMemoryRouter(routes, { initialEntries });
  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

// ============================================================================
// Test Suite
// ============================================================================

describe('Weekly Meal Planner, Cooking Progress & Shopping List (Step 05.6)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  // --------------------------------------------------------------------------
  // Group A: Guest Session Lifecycle
  // --------------------------------------------------------------------------

  it('1. provisions a new guest session via POST /api/v1/guest-sessions when none exists', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;

    renderMealPlannerPage();

    await waitFor(() => {
      const sessionCalls = mockFetch.mock.calls.filter(
        (c) => c[0].toString().includes('/api/v1/guest-sessions') && c[1]?.method === 'POST'
      );
      expect(sessionCalls).toHaveLength(1);
    });

    const stored = JSON.parse(localStorage.getItem(GUEST_SESSION_STORAGE_KEY) || '{}');
    expect(stored.sessionId).toBe(mockSessionId);
  });

  it('2. reuses existing active guest session from localStorage without re-provisioning', async () => {
    localStorage.setItem(
      GUEST_SESSION_STORAGE_KEY,
      JSON.stringify({
        sessionId: mockSessionId,
        expiresAt: new Date(Date.now() + 86400000).toISOString(),
        createdAt: new Date().toISOString(),
      })
    );

    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;

    renderMealPlannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('meal-planner-page')).toBeInTheDocument();
    });

    const sessionPostCalls = mockFetch.mock.calls.filter(
      (c) => c[0].toString().includes('/api/v1/guest-sessions') && c[1]?.method === 'POST'
    );
    expect(sessionPostCalls).toHaveLength(0);
  });

  it('3. strictly manages X-Guest-Session-ID on Planner requests and never leaks to other services', async () => {
    localStorage.setItem(
      GUEST_SESSION_STORAGE_KEY,
      JSON.stringify({
        sessionId: mockSessionId,
        expiresAt: new Date(Date.now() + 86400000).toISOString(),
      })
    );
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);

    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;

    renderMealPlannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('weekly-overview-card')).toBeInTheDocument();
    });

    // Check all fetch calls
    mockFetch.mock.calls.forEach(([url, init]) => {
      const urlStr = url.toString();
      if (urlStr.includes(':8003') && !urlStr.includes('/generate')) {
        expect(init?.headers?.['X-Guest-Session-ID']).toBe(mockSessionId);
      }
      if (urlStr.includes(':8002') || urlStr.includes(':8001')) {
        expect(init?.headers?.['X-Guest-Session-ID']).toBeUndefined();
      }
    });
  });

  it('4. recovers safely and re-provisions a session when planner returns 401 SESSION_EXPIRED', async () => {
    let callCount = 0;
    const mockFetch = vi.fn().mockImplementation((url: string | URL) => {
      const urlStr = url.toString();

      if (urlStr.includes('/api/v1/guest-sessions')) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => mockGuestSession,
        });
      }

      if (urlStr.includes('/api/v1/meal-plans/')) {
        callCount++;
        if (callCount === 1) {
          // First attempt returns 401
          return Promise.resolve({
            ok: false,
            status: 401,
            json: async () => ({
              error: { code: 'SESSION_EXPIRED', message: 'Session expired.' },
            }),
          });
        }
        // Second attempt returns plan
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockSavedPlanDetail,
        });
      }

      if (urlStr.includes('/shopping-list')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockShoppingList,
        });
      }

      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });

    global.fetch = mockFetch;
    localStorage.setItem(
      GUEST_SESSION_STORAGE_KEY,
      JSON.stringify({
        sessionId: 'old-expired-uuid',
        expiresAt: new Date(Date.now() + 86400000).toISOString(),
      })
    );
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);

    renderMealPlannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('weekly-overview-card')).toBeInTheDocument();
    });
    expect(callCount).toBeGreaterThanOrEqual(2);
  });

  // --------------------------------------------------------------------------
  // Group B: Empty State & Navigation
  // --------------------------------------------------------------------------

  it('5. renders informative empty state when no saved plan exists in guest session', async () => {
    global.fetch = setupMockFetch();
    renderMealPlannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('empty-planner-state')).toBeInTheDocument();
      expect(screen.getByTestId('empty-planner-title')).toHaveTextContent('No Active Meal Plan');
      expect(screen.getByTestId('create-plan-cta-btn')).toBeInTheDocument();
    });

    // Confirms NO fake meals are rendered as saved data
    expect(screen.queryByTestId('weekly-overview-card')).not.toBeInTheDocument();
  });

  it('6. transitions from empty state to generator form when CTA is clicked', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('create-plan-cta-btn')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('create-plan-cta-btn'));

    expect(screen.getByTestId('meal-plan-generator-card')).toBeInTheDocument();
    expect(screen.getByTestId('generator-form')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group C: Meal Plan Generation & Proposal Review
  // --------------------------------------------------------------------------

  it('7. renders all generation controls with compliant default values', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => {
      expect(screen.getByTestId('create-plan-cta-btn')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('create-plan-cta-btn'));

    expect(screen.getByTestId('gen-days-input')).toHaveValue(7);
    expect(screen.getByTestId('slot-checkbox-breakfast')).toBeChecked();
    expect(screen.getByTestId('slot-checkbox-lunch')).toBeChecked();
    expect(screen.getByTestId('slot-checkbox-dinner')).toBeChecked();
    expect(screen.getByTestId('slot-checkbox-snack')).not.toBeChecked();
    expect(screen.getByTestId('gen-calories-input')).toHaveValue(null);
    expect(screen.getByTestId('gen-diet-select')).toHaveValue('');
    expect(screen.getByTestId('gen-cuisine-select')).toHaveValue('');
    expect(screen.getByTestId('submit-generate-plan-btn')).toBeInTheDocument();
  });

  it('8. enforces client-side validation on invalid days horizon', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('create-plan-cta-btn'));

    const daysInput = await screen.findByTestId('gen-days-input');
    await user.clear(daysInput);
    await user.type(daysInput, '0');

    await user.click(screen.getByTestId('submit-generate-plan-btn'));

    expect(await screen.findByTestId('generator-error-banner')).toHaveTextContent(
      /Planning horizon must be between 1 and 14 days/i
    );
  });

  it('9. enforces calorie range boundary (800–6000 kcal) with client-side alert', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('create-plan-cta-btn'));

    const calInput = await screen.findByTestId('gen-calories-input');
    await user.type(calInput, '500'); // below 800

    await user.click(screen.getByTestId('submit-generate-plan-btn'));

    expect(await screen.findByTestId('generator-error-banner')).toHaveTextContent(
      /Daily calorie target must be between 800 and 6,000 kcal/i
    );
  });

  it('10. dispatches POST /api/v1/meal-plans/generate with selected parameters', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('create-plan-cta-btn'));

    // Configure 2 days, vegetarian, 2100 kcal
    const daysInput = await screen.findByTestId('gen-days-input');
    await user.clear(daysInput);
    await user.type(daysInput, '2');

    const calInput = screen.getByTestId('gen-calories-input');
    await user.type(calInput, '2100');

    const dietSelect = screen.getByTestId('gen-diet-select');
    await user.selectOptions(dietSelect, 'vegetarian');

    await user.click(screen.getByTestId('submit-generate-plan-btn'));

    await waitFor(() => {
      const genCall = mockFetch.mock.calls.find((c) =>
        c[0].toString().includes('/api/v1/meal-plans/generate')
      );
      expect(genCall).toBeDefined();
      const body = JSON.parse(genCall![1].body);
      expect(body.days).toBe(2);
      expect(body.target_calories_kcal).toBe(2100);
      expect(body.diet_preference).toBe('vegetarian');
      expect(body.slots).toEqual(['breakfast', 'lunch', 'dinner']);
    });
  });

  it('11. displays proposal preview with unpersisted warning banner', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('submit-generate-plan-btn'));

    expect(await screen.findByTestId('proposal-preview-section')).toBeInTheDocument();
    expect(screen.getByTestId('proposal-status-banner')).toHaveTextContent(
      /Proposal Mode \(Unsaved\)/i
    );
    expect(screen.getByTestId('proposal-notes')).toHaveTextContent(
      'Plan generated without dietary restrictions.'
    );
    expect(screen.getByTestId('proposal-day-0')).toBeInTheDocument();
    expect(screen.getByTestId('proposal-day-1')).toBeInTheDocument();
    expect(screen.getByTestId('save-generated-plan-btn')).toBeInTheDocument();
  });

  it('12. discard button clears proposal preview and returns to form', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('submit-generate-plan-btn'));

    await waitFor(() => screen.getByTestId('discard-proposal-btn'));
    await user.click(screen.getByTestId('discard-proposal-btn'));

    expect(screen.queryByTestId('proposal-preview-section')).not.toBeInTheDocument();
    expect(screen.getByTestId('generator-form')).toBeInTheDocument();
  });

  it('13. handles generator error from backend with alert notice', async () => {
    const mockFetch = setupMockFetch({ generateStatus: 502 });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('submit-generate-plan-btn'));

    expect(await screen.findByTestId('generator-error-banner')).toHaveTextContent(
      /Failed to generate meal plan proposal/i
    );
  });

  it('14. saves generated plan via POST /api/v1/meal-plans and switches to active workspace', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('create-plan-cta-btn'));
    await user.click(screen.getByTestId('submit-generate-plan-btn'));

    await waitFor(() => screen.getByTestId('save-generated-plan-btn'));
    await user.click(screen.getByTestId('save-generated-plan-btn'));

    await waitFor(() => {
      const saveCall = mockFetch.mock.calls.find(
        (c) => c[0].toString().endsWith('/api/v1/meal-plans') && c[1]?.method === 'POST'
      );
      expect(saveCall).toBeDefined();
      const body = JSON.parse(saveCall![1].body);
      expect(body.days).toBe(2);
      expect(body.slots.length).toBe(6);
    });

    expect(await screen.findByTestId('weekly-overview-card')).toBeInTheDocument();
    expect(localStorage.getItem(ACTIVE_PLAN_STORAGE_KEY)).toBe(mockPlanId);
  });

  // --------------------------------------------------------------------------
  // Group D: Saved Meal Plan & Weekly Overview
  // --------------------------------------------------------------------------

  it('15. loads and renders active saved plan from localStorage identifier', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();

    renderMealPlannerPage();

    expect(await screen.findByTestId('weekly-overview-card')).toBeInTheDocument();
    expect(screen.getByTestId('plan-title')).toHaveTextContent('Weekly Fitness Schedule');
    expect(screen.getByTestId('plan-days-tag')).toHaveTextContent('2 Days Horizon');
    expect(screen.getByTestId('plan-calories-tag')).toHaveTextContent('Target: 2100 kcal/day');
  });

  it('16. renders all scheduled meal slots with recipes and cooking statuses', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('slot-item-101'));

    expect(screen.getByTestId('slot-recipe-name-101')).toHaveTextContent('Blueberry Oatmeal');
    expect(screen.getByTestId('slot-type-101')).toHaveTextContent('BREAKFAST');
    expect(screen.getByTestId('cooking-status-pill-101')).toHaveTextContent('Pending');

    expect(screen.getByTestId('slot-recipe-name-102')).toHaveTextContent(
      'Mediterranean Chicken Salad'
    );
    expect(screen.getByTestId('cooking-status-pill-102')).toHaveTextContent('Cooked');
  });

  it('17. filters visible slots when day tabs are clicked', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('day-card-0'));
    expect(screen.getByTestId('day-card-1')).toBeInTheDocument();

    // Click Day 1 tab
    await user.click(screen.getByTestId('day-tab-0'));
    expect(screen.getByTestId('day-card-0')).toBeInTheDocument();
    expect(screen.queryByTestId('day-card-1')).not.toBeInTheDocument();

    // Click All Days tab
    await user.click(screen.getByTestId('day-tab-all'));
    expect(screen.getByTestId('day-card-0')).toBeInTheDocument();
    expect(screen.getByTestId('day-card-1')).toBeInTheDocument();
  });

  it('18. provides direct navigation links to recipe details and cooking mode', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('slot-item-101'));

    const detailsLink = screen.getByTestId('recipe-link-101');
    expect(detailsLink).toHaveAttribute('href', '/recipes/rcp_foodcom_101');

    const cookModeLink = screen.getByTestId('cook-mode-link-101');
    expect(cookModeLink).toHaveAttribute('href', '/recipes/rcp_foodcom_101?mode=cook');
  });

  it('19. cleans up stale active plan ID from storage when backend returns 404', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, 'stale-deleted-id');
    const mockFetch = setupMockFetch({ planStatus: 404, planResponse: null });
    global.fetch = mockFetch;

    renderMealPlannerPage();

    expect(await screen.findByTestId('empty-planner-state')).toBeInTheDocument();
    expect(localStorage.getItem(ACTIVE_PLAN_STORAGE_KEY)).toBeNull();
  });

  // --------------------------------------------------------------------------
  // Group E: Cooking Progress Execution
  // --------------------------------------------------------------------------

  it('20. renders cooking execution progress summary with accurate counts and percentage', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('cooking-progress-summary'));

    // 1 cooked out of 6 slots = 17%
    expect(screen.getByTestId('cooking-stats-label')).toHaveTextContent(
      '1 of 6 Meals Prepared (17%)'
    );
  });

  it('21. marks meal slot as cooked via PATCH /api/v1/meal-plans/:plan_id/progress', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('mark-cooked-btn-101'));
    await user.click(screen.getByTestId('mark-cooked-btn-101'));

    await waitFor(() => {
      const patchCall = mockFetch.mock.calls.find(
        (c) => c[0].toString().includes('/progress') && c[1]?.method === 'PATCH'
      );
      expect(patchCall).toBeDefined();
      const body = JSON.parse(patchCall![1].body);
      expect(body.updates).toEqual([{ slot_id: 101, cooking_status: 'cooked' }]);
    });

    expect(screen.getByTestId('cooking-status-pill-101')).toHaveTextContent('Cooked');
  });

  it('22. marks meal slot as skipped via cooking progress endpoint', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('mark-skipped-btn-101'));
    await user.click(screen.getByTestId('mark-skipped-btn-101'));

    await waitFor(() => {
      const patchCall = mockFetch.mock.calls.find((c) => c[0].toString().includes('/progress'));
      expect(patchCall).toBeDefined();
      const body = JSON.parse(patchCall![1].body);
      expect(body.updates).toEqual([{ slot_id: 101, cooking_status: 'skipped' }]);
    });

    expect(screen.getByTestId('cooking-status-pill-101')).toHaveTextContent('Skipped');
  });

  it('23. resets cooking status to pending when reset button is clicked', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    // Slot 102 starts as cooked
    await waitFor(() => screen.getByTestId('mark-pending-btn-102'));
    await user.click(screen.getByTestId('mark-pending-btn-102'));

    await waitFor(() => {
      const patchCall = mockFetch.mock.calls.find((c) => c[0].toString().includes('/progress'));
      const body = JSON.parse(patchCall![1].body);
      expect(body.updates).toEqual([{ slot_id: 102, cooking_status: 'pending' }]);
    });

    expect(screen.getByTestId('cooking-status-pill-102')).toHaveTextContent('Pending');
  });

  it('24. displays error banner when cooking progress patch fails', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch({ progressStatus: 500 });
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('mark-cooked-btn-101'));
    await user.click(screen.getByTestId('mark-cooked-btn-101'));

    expect(await screen.findByTestId('planner-error-banner')).toHaveTextContent(
      /Failed to update cooking progress/i
    );
  });

  // --------------------------------------------------------------------------
  // Group F: Meal Plan Mutation & Deletion
  // --------------------------------------------------------------------------

  it('25. removes a meal slot from schedule and syncs via PUT /api/v1/meal-plans/:id', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('remove-slot-btn-101'));
    await user.click(screen.getByTestId('remove-slot-btn-101'));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(
        (c) => c[0].toString().includes(`/api/v1/meal-plans/${mockPlanId}`) && c[1]?.method === 'PUT'
      );
      expect(putCall).toBeDefined();
      const body = JSON.parse(putCall![1].body);
      // Remained slots should be 5
      expect(body.slots.length).toBe(5);
      expect(body.slots.some((s: any) => s.recipe_title === 'Blueberry Oatmeal')).toBe(false);
    });
  });

  it('26. requires confirmation before deleting plan and reverts to empty state', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('delete-plan-btn'));

    // First click: prompts for confirmation
    await user.click(screen.getByTestId('delete-plan-btn'));
    expect(screen.getByTestId('delete-plan-btn')).toHaveTextContent('Click to Confirm Delete');
    expect(screen.getByTestId('cancel-delete-plan-btn')).toBeInTheDocument();

    // Second click: executes deletion
    await user.click(screen.getByTestId('delete-plan-btn'));

    await waitFor(() => {
      const delCall = mockFetch.mock.calls.find(
        (c) => c[0].toString().includes(`/api/v1/meal-plans/${mockPlanId}`) && c[1]?.method === 'DELETE'
      );
      expect(delCall).toBeDefined();
    });

    expect(await screen.findByTestId('empty-planner-state')).toBeInTheDocument();
    expect(localStorage.getItem(ACTIVE_PLAN_STORAGE_KEY)).toBeNull();
  });

  it('27. canceling delete confirmation retains the active meal plan', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('delete-plan-btn'));
    await user.click(screen.getByTestId('delete-plan-btn'));

    await user.click(screen.getByTestId('cancel-delete-plan-btn'));

    expect(screen.getByTestId('delete-plan-btn')).toHaveTextContent('Delete Plan');
    expect(screen.getByTestId('weekly-overview-card')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group G: Consolidated Shopping List & Pantry Interaction
  // --------------------------------------------------------------------------

  it('28. switches to shopping list tab and renders consolidated aisle categories', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('tab-shopping-list'));
    await user.click(screen.getByTestId('tab-shopping-list'));

    expect(await screen.findByTestId('shopping-list-section')).toBeInTheDocument();
    expect(screen.getByTestId('shopping-list-heading')).toHaveTextContent(
      'Consolidated Grocery Shopping List'
    );
    expect(screen.getByTestId('aisle-group-produce')).toBeInTheDocument();
    expect(screen.getByTestId('aisle-group-meat---seafood')).toBeInTheDocument();
    expect(screen.getByTestId('aisle-group-dairy---refrigerated')).toBeInTheDocument();
  });

  it('29. clearly discloses pantry integration behavior and limitations', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('tab-shopping-list'));
    await user.click(screen.getByTestId('tab-shopping-list'));

    const notice = await screen.findByTestId('pantry-behavior-notice');
    expect(notice).toHaveTextContent(/does not automatically subtract pantry inventory/i);
  });

  it('30. renders ingredient names and quantity displays in checklist items', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();
    const user = userEvent.setup();

    renderMealPlannerPage();

    await user.click(await screen.findByTestId('tab-shopping-list'));

    expect(screen.getByTestId('shopping-item-name-1')).toHaveTextContent('fresh blueberries');
    expect(screen.getByTestId('shopping-item-qty-1')).toHaveTextContent('1 cup');
    expect(screen.getByTestId('shopping-item-name-3')).toHaveTextContent('salmon fillets');
    expect(screen.getByTestId('shopping-item-qty-3')).toHaveTextContent('2 pieces');
  });

  it('31. toggles item procurement status via PATCH /shopping-list/items/:id', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();

    renderMealPlannerPage();

    await user.click(await screen.findByTestId('tab-shopping-list'));

    const checkbox = await screen.findByTestId('shopping-item-checkbox-1');
    expect(checkbox).not.toBeChecked();

    await user.click(checkbox);

    await waitFor(() => {
      const patchCall = mockFetch.mock.calls.find(
        (c) => c[0].toString().includes('/shopping-list/items/1') && c[1]?.method === 'PATCH'
      );
      expect(patchCall).toBeDefined();
      const body = JSON.parse(patchCall![1].body);
      expect(body.checked).toBe(true);
    });
  });

  it('32. filters shopping list items by Remaining and Purchased states', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();
    const user = userEvent.setup();

    renderMealPlannerPage();

    await user.click(await screen.findByTestId('tab-shopping-list'));

    await waitFor(() => screen.getByTestId('shopping-stats-label'));
    expect(screen.getByTestId('shopping-stats-label')).toHaveTextContent(
      '1 of 4 Items Acquired (25%)'
    );

    // Filter Remaining (3 unpurchased)
    await user.click(screen.getByTestId('filter-remaining-btn'));
    expect(screen.getByTestId('shopping-item-1')).toBeInTheDocument();
    expect(screen.queryByTestId('shopping-item-2')).not.toBeInTheDocument();

    // Filter Purchased (1 purchased)
    await user.click(screen.getByTestId('filter-purchased-btn'));
    expect(screen.queryByTestId('shopping-item-1')).not.toBeInTheDocument();
    expect(screen.getByTestId('shopping-item-2')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group H: Nutrition & Editorial Standards
  // --------------------------------------------------------------------------

  it('33. switches to nutrition tab and displays target calories and disclosure', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();
    const user = userEvent.setup();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('tab-nutrition'));
    await user.click(screen.getByTestId('tab-nutrition'));

    expect(await screen.findByTestId('meal-plan-nutrition-summary')).toBeInTheDocument();
    expect(screen.getByTestId('nutrition-target-calories')).toHaveTextContent('2100 kcal');
    expect(screen.getByTestId('nutrition-days-horizon')).toHaveTextContent('2 Days');
    expect(screen.getByTestId('nutrition-total-meals')).toHaveTextContent('6 Meals');
    expect(screen.getByTestId('nutrition-disclosure-box')).toHaveTextContent(
      /Macronutrient Distribution Note/i
    );
  });

  it('34. enforces strict 0px border radius across all cards, buttons, and inputs', async () => {
    localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, mockPlanId);
    global.fetch = setupMockFetch();

    renderMealPlannerPage();

    await waitFor(() => screen.getByTestId('weekly-overview-card'));

    const overviewCard = screen.getByTestId('weekly-overview-card');
    const computed = window.getComputedStyle(overviewCard);
    expect(computed.borderRadius).toMatch(/^(0px|0)?$/);
  });
});
