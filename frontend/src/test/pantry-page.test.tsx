import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { routes } from '../router';
import { ThemeProvider } from '../theme/ThemeContext';
import {
  GuestSession,
  PantryInventoryResponse,
  PantryItem,
  PantryMatchResponse,
} from '../api/types/planner';
import { IngredientSuggestion } from '../api/types/recipe';
import { GUEST_SESSION_STORAGE_KEY } from '../utils/guestSession';

// ============================================================================
// Mock Data
// ============================================================================

const mockSessionId = 'e4eaaaf2-d142-4f01-9e73-b3c990b79f82';

const mockGuestSession: GuestSession = {
  session_id: mockSessionId,
  created_at: '2026-11-03T07:00:00Z',
  expires_at: '2026-12-03T07:00:00Z',
  last_active_at: '2026-11-03T07:00:00Z',
};

const mockSuggestions: IngredientSuggestion[] = [
  {
    id: 101,
    name: 'chicken breast',
    category: 'poultry',
    is_pantry_staple: false,
  },
  {
    id: 10,
    name: 'garlic clove',
    category: 'vegetables',
    is_pantry_staple: false,
  },
  {
    id: 50,
    name: 'olive oil',
    category: 'fats_oils',
    is_pantry_staple: true,
  },
];

const mockPantryItems: PantryItem[] = [
  {
    id: 1,
    raw_name: '2 lbs chicken breast',
    canonical_ingredient_id: 101,
    created_at: '2026-11-03T07:00:00Z',
  },
  {
    id: 2,
    raw_name: '4 cloves garlic',
    canonical_ingredient_id: 10,
    created_at: '2026-11-03T07:05:00Z',
  },
];

const mockEmptyPantryResponse: PantryInventoryResponse = {
  items: [],
  total_count: 0,
};

const mockPopulatedPantryResponse: PantryInventoryResponse = {
  items: mockPantryItems,
  total_count: 2,
};

const mockMatchResponse: PantryMatchResponse = {
  matches: [
    {
      recipe_id: 'rcp_foodcom_5421',
      title: 'Classic Rosemary Garlic Roasted Chicken',
      match_pct: 66.7,
      matched_ingredients: ['2 lbs chicken breast', '4 cloves garlic'],
      missing_ingredients: ['2 tbsp fresh rosemary'],
      total_recipe_ingredients: 3,
      total_time_minutes: 75,
      rating_average: 4.8,
    },
    {
      recipe_id: 'rcp_nlg_1914325',
      title: 'Skillet Garlic Chicken Cutlets',
      match_pct: 50.0,
      matched_ingredients: ['chicken breast'],
      missing_ingredients: ['butter', 'lemon juice'],
      total_recipe_ingredients: 4,
      total_time_minutes: 25,
      rating_average: 4.2,
    },
  ],
  pagination: {
    page: 1,
    limit: 12,
    total_items: 2,
    total_pages: 1,
  },
};

const mockEmptyMatchResponse: PantryMatchResponse = {
  matches: [],
  pagination: {
    page: 1,
    limit: 12,
    total_items: 0,
    total_pages: 0,
  },
};

// ============================================================================
// Setup Mock Fetch Handler
// ============================================================================

interface MockFetchOptions {
  sessionStatus?: number;
  sessionResponse?: GuestSession;
  pantryStatus?: number;
  pantryResponse?: PantryInventoryResponse;
  updatePantryStatus?: number;
  suggestionsStatus?: number;
  suggestionsResponse?: IngredientSuggestion[];
  matchStatus?: number;
  matchResponse?: PantryMatchResponse;
}

function setupMockFetch(options: MockFetchOptions = {}) {
  const {
    sessionStatus = 201,
    sessionResponse = mockGuestSession,
    pantryStatus = 200,
    pantryResponse = mockPopulatedPantryResponse,
    updatePantryStatus = 200,
    suggestionsStatus = 200,
    suggestionsResponse = mockSuggestions,
    matchStatus = 200,
    matchResponse = mockMatchResponse,
  } = options;

  let currentPantry = [...pantryResponse.items];

  return vi.fn().mockImplementation((url: string | URL, init?: RequestInit) => {
    const urlStr = url.toString();
    const method = init?.method?.toUpperCase() || 'GET';

    // 1. Guest Session endpoint POST /api/v1/guest-sessions
    if (urlStr.includes('/api/v1/guest-sessions') && method === 'POST') {
      if (sessionStatus === 201 || sessionStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 201,
          json: async () => sessionResponse,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: sessionStatus,
          statusText: 'Internal Server Error',
          json: async () => ({
            error: { code: 'SESSION_CREATE_FAILED', message: 'Failed to create guest session.' },
          }),
        });
      }
    }

    // 2. Guest Session touch endpoint GET /api/v1/guest-sessions/{session_id}
    if (urlStr.match(/\/api\/v1\/guest-sessions\/[0-9a-fA-F-]+/) && method === 'GET') {
      if (sessionStatus === 200 || sessionStatus === 201) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => sessionResponse,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: 404,
          statusText: 'Not Found',
          json: async () => ({
            error: { code: 'SESSION_EXPIRED', message: 'Guest session expired.' },
          }),
        });
      }
    }

    // 3. Ingredient Suggestions GET /api/v1/ingredients/suggestions
    if (urlStr.includes('/api/v1/ingredients/suggestions')) {
      if (suggestionsStatus === 200) {
        const urlObj = new URL(urlStr);
        const q = urlObj.searchParams.get('q') || '';
        if (q.toLowerCase().includes('nonexistent') || q.toLowerCase().includes('xyz')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => [],
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => suggestionsResponse,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: suggestionsStatus,
          statusText: 'Internal Server Error',
          json: async () => ({
            error: { code: 'SUGGESTION_ERROR', message: 'Failed to fetch suggestions.' },
          }),
        });
      }
    }

    // 4. Pantry Inventory GET /api/v1/pantry
    if (urlStr.includes('/api/v1/pantry') && method === 'GET') {
      if (pantryStatus === 200) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ items: currentPantry, total_count: currentPantry.length }),
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: pantryStatus,
          statusText: pantryStatus === 401 ? 'Unauthorized' : 'Internal Server Error',
          json: async () => ({
            error: {
              code: pantryStatus === 401 ? 'SESSION_EXPIRED' : 'PANTRY_ERROR',
              message: 'Pantry error occurred.',
            },
          }),
        });
      }
    }

    // 5. Pantry Inventory PUT /api/v1/pantry
    if (urlStr.includes('/api/v1/pantry') && method === 'PUT') {
      if (updatePantryStatus === 200) {
        const body = JSON.parse(init?.body as string);
        const newItems: PantryItem[] = (body.items || []).map((it: any, idx: number) => ({
          id: idx + 1,
          raw_name: it.raw_name,
          canonical_ingredient_id: it.canonical_ingredient_id ?? null,
          created_at: new Date().toISOString(),
        }));
        currentPantry = newItems;
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ items: currentPantry, total_count: currentPantry.length }),
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: updatePantryStatus,
          statusText: 'Internal Server Error',
          json: async () => ({
            error: { code: 'UPDATE_PANTRY_FAILED', message: 'Failed to replace pantry items.' },
          }),
        });
      }
    }

    // 6. Pantry Matching POST /api/v1/pantry/match
    if (urlStr.includes('/api/v1/pantry/match') && method === 'POST') {
      if (matchStatus === 200) {
        const body = JSON.parse(init?.body as string);
        if (body.min_match_pct >= 90) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: async () => mockEmptyMatchResponse,
          });
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => matchResponse,
        });
      } else {
        return Promise.resolve({
          ok: false,
          status: matchStatus,
          statusText: 'Internal Server Error',
          json: async () => ({
            error: { code: 'MATCH_ERROR', message: 'Failed to calculate pantry recipe match.' },
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

function renderPantryPage(initialPath = '/pantry') {
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
// Test Suite: Step 05.5 Guest Pantry & Recipe Ingredient Matching
// ============================================================================

describe('Guest Pantry Management & Recipe Ingredient Matching (Step 05.5)', () => {
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
  // Group A: Guest Session Lifecycle
  // --------------------------------------------------------------------------

  it('1. provisions a new guest session via POST /api/v1/guest-sessions when none exists', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-page')).toBeInTheDocument();
    });

    const sessionCall = mockFetch.mock.calls.find((c) =>
      c[0].toString().includes('/api/v1/guest-sessions')
    );
    expect(sessionCall).toBeDefined();
    expect(sessionCall![1].method).toBe('POST');

    // Verify session stored in localStorage
    const stored = JSON.parse(localStorage.getItem(GUEST_SESSION_STORAGE_KEY) || '{}');
    expect(stored.sessionId).toBe(mockSessionId);
  });

  it('2. reuses existing unexpired guest session from localStorage without calling POST', async () => {
    localStorage.setItem(
      GUEST_SESSION_STORAGE_KEY,
      JSON.stringify({
        sessionId: 'existing-valid-session-1234',
        expiresAt: new Date(Date.now() + 86400000).toISOString(), // 24h future
        createdAt: new Date().toISOString(),
      })
    );

    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-page')).toBeInTheDocument();
    });

    const createCall = mockFetch.mock.calls.find(
      (c) => c[0].toString().includes('/api/v1/guest-sessions') && c[1]?.method === 'POST'
    );
    expect(createCall).toBeUndefined();

    // Verify pantry called with existing session ID
    const pantryCall = mockFetch.mock.calls.find((c) => c[0].toString().includes('/api/v1/pantry'));
    expect(pantryCall).toBeDefined();
    expect(pantryCall![1].headers['X-Guest-Session-ID']).toBe('existing-valid-session-1234');
  });

  it('3. detects expired session timestamp and automatically provisions a fresh session', async () => {
    localStorage.setItem(
      GUEST_SESSION_STORAGE_KEY,
      JSON.stringify({
        sessionId: 'expired-session-999',
        expiresAt: new Date(Date.now() - 3600000).toISOString(), // 1h past
        createdAt: new Date().toISOString(),
      })
    );

    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-page')).toBeInTheDocument();
    });

    const createCall = mockFetch.mock.calls.find(
      (c) => c[0].toString().includes('/api/v1/guest-sessions') && c[1]?.method === 'POST'
    );
    expect(createCall).toBeDefined();
  });

  it('4. prevents multiple simultaneous session creation requests', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;

    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-page')).toBeInTheDocument();
    });

    const createCalls = mockFetch.mock.calls.filter(
      (c) => c[0].toString().includes('/api/v1/guest-sessions') && c[1]?.method === 'POST'
    );
    expect(createCalls.length).toBe(1);
  });

  it('5. handles guest session creation failure gracefully with error feedback and retry', async () => {
    const mockFetch = setupMockFetch({ sessionStatus: 500 });
    global.fetch = mockFetch;
    renderPantryPage();

    expect(await screen.findByTestId('pantry-error')).toBeInTheDocument();
    expect(screen.getByTestId('pantry-retry-btn')).toBeInTheDocument();
  });

  it('6. recovers and provisions a new session when Planner returns 401 SESSION_EXPIRED', async () => {
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

      if (urlStr.includes('/api/v1/pantry')) {
        callCount++;
        if (callCount === 1) {
          // First attempt returns 401
          return Promise.resolve({
            ok: false,
            status: 401,
            json: async () => ({
              error: { code: 'SESSION_EXPIRED', message: 'Session expired' },
            }),
          });
        }
        // Second attempt succeeds
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockPopulatedPantryResponse,
        });
      }

      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    global.fetch = mockFetch;
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-items-list')).toBeInTheDocument();
    });

    expect(callCount).toBe(2);
  });

  // --------------------------------------------------------------------------
  // Group B: Canonical Ingredient Search & Suggestions
  // --------------------------------------------------------------------------

  it('7. renders ingredient search input with taxonomy guidance', async () => {
    global.fetch = setupMockFetch();
    renderPantryPage();

    expect(screen.getByTestId('pantry-add-ingredient-card')).toBeInTheDocument();
    expect(screen.getByTestId('ingredient-search-input')).toBeInTheDocument();
    expect(screen.getByTestId('add-ingredient-btn')).toBeDisabled();
    expect(screen.getByText(/Search our 106-canonical ingredient taxonomy/i)).toBeInTheDocument();
  });

  it('8. queries GET /api/v1/ingredients/suggestions on typing', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    const input = screen.getByTestId('ingredient-search-input');
    await user.type(input, 'chick');

    await waitFor(() => {
      expect(screen.getByTestId('suggestions-dropdown')).toBeInTheDocument();
    });

    const suggestionCall = mockFetch.mock.calls.find((c) =>
      c[0].toString().includes('/api/v1/ingredients/suggestions')
    );
    expect(suggestionCall).toBeDefined();
    expect(suggestionCall![0].toString()).toContain('q=chick');
  });

  it('9. displays suggestions with canonical ID, category, and staple status', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderPantryPage();

    await user.type(screen.getByTestId('ingredient-search-input'), 'chick');

    await waitFor(() => {
      expect(screen.getByTestId('suggestions-dropdown')).toBeInTheDocument();
    });

    expect(screen.getByTestId('suggestion-item-101')).toHaveTextContent('chicken breast');
    expect(screen.getByTestId('suggestion-item-101')).toHaveTextContent('ID: #101');
    expect(screen.getByTestId('suggestion-item-101')).toHaveTextContent('poultry');
    expect(screen.getByTestId('suggestion-item-50')).toHaveTextContent('Staple');
  });

  it('10. selects a suggestion, locks canonical ID, and enables add button', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderPantryPage();

    await user.type(screen.getByTestId('ingredient-search-input'), 'chick');

    await waitFor(() => {
      expect(screen.getByTestId('suggestion-item-101')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('suggestion-item-101'));

    expect(screen.getByTestId('selected-ingredient-pill')).toBeInTheDocument();
    expect(screen.getByTestId('selected-ingredient-pill')).toHaveTextContent('Canonical #101');
    expect(screen.getByTestId('selected-ingredient-pill')).toHaveTextContent('chicken breast');
    expect(screen.getByTestId('add-ingredient-btn')).not.toBeDisabled();
  });

  it('11. clears selected suggestion when clear button is clicked', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderPantryPage();

    await user.type(screen.getByTestId('ingredient-search-input'), 'chick');

    await waitFor(() => {
      expect(screen.getByTestId('suggestion-item-101')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('suggestion-item-101'));
    expect(screen.getByTestId('clear-selection-btn')).toBeInTheDocument();

    await user.click(screen.getByTestId('clear-selection-btn'));

    expect(screen.queryByTestId('selected-ingredient-pill')).not.toBeInTheDocument();
    expect((screen.getByTestId('ingredient-search-input') as HTMLInputElement).value).toBe('');
    expect(screen.getByTestId('add-ingredient-btn')).toBeDisabled();
  });

  it('12. displays empty suggestions state when ingredient is not in canonical taxonomy', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderPantryPage();

    await user.type(screen.getByTestId('ingredient-search-input'), 'nonexistentfood');

    await waitFor(() => {
      expect(screen.getByTestId('suggestions-empty')).toBeInTheDocument();
    });

    expect(screen.getByTestId('suggestions-empty')).toHaveTextContent(
      /No canonical ingredient matching “nonexistentfood” was found in the taxonomy/i
    );
  });

  it('13. handles suggestion query error gracefully', async () => {
    global.fetch = setupMockFetch({ suggestionsStatus: 500 });
    const user = userEvent.setup();
    renderPantryPage();

    await user.type(screen.getByTestId('ingredient-search-input'), 'garlic');

    expect(await screen.findByTestId('suggestions-error')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group C: Pantry Inventory Management
  // --------------------------------------------------------------------------

  it('14. loads and displays existing pantry items on mount from GET /api/v1/pantry', async () => {
    global.fetch = setupMockFetch();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-items-list')).toBeInTheDocument();
    });

    expect(screen.getByTestId('inventory-count-badge')).toHaveTextContent('2 Items');
    expect(screen.getByTestId('item-name-1')).toHaveTextContent('2 lbs chicken breast');
    expect(screen.getByTestId('item-canonical-1')).toHaveTextContent('Canonical #101');
    expect(screen.getByTestId('item-name-2')).toHaveTextContent('4 cloves garlic');
  });

  it('15. displays empty pantry state when inventory contains zero items', async () => {
    global.fetch = setupMockFetch({ pantryResponse: mockEmptyPantryResponse });
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-empty-state')).toBeInTheDocument();
    });

    expect(screen.getByText('Your Pantry is Empty')).toBeInTheDocument();
    expect(screen.getByTestId('inventory-count-badge')).toHaveTextContent('0 Items');
  });

  it('16. adds an ingredient with canonical ID via PUT /api/v1/pantry appending to inventory', async () => {
    const mockFetch = setupMockFetch({ pantryResponse: mockEmptyPantryResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-empty-state')).toBeInTheDocument();
    });

    await user.type(screen.getByTestId('ingredient-search-input'), 'chick');
    await waitFor(() => {
      expect(screen.getByTestId('suggestion-item-101')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('suggestion-item-101'));
    await user.click(screen.getByTestId('add-ingredient-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('pantry-items-list')).toBeInTheDocument();
    });

    const putCall = mockFetch.mock.calls.find(
      (c) => c[0].toString().includes('/api/v1/pantry') && c[1]?.method === 'PUT'
    );
    expect(putCall).toBeDefined();
    const payload = JSON.parse(putCall![1].body);
    expect(payload.items).toHaveLength(1);
    expect(payload.items[0]).toEqual({
      raw_name: 'chicken breast',
      canonical_ingredient_id: 101,
    });
  });

  it('17. formats raw text with optional quantity and unit when entered', async () => {
    const mockFetch = setupMockFetch({ pantryResponse: mockEmptyPantryResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-empty-state')).toBeInTheDocument();
    });

    await user.type(screen.getByTestId('ingredient-search-input'), 'olive oil');
    await waitFor(() => {
      expect(screen.getByTestId('suggestion-item-50')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('suggestion-item-50'));

    await user.type(screen.getByTestId('ingredient-quantity-input'), '500');
    await user.type(screen.getByTestId('ingredient-unit-input'), 'ml');

    await user.click(screen.getByTestId('add-ingredient-btn'));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(
        (c) => c[0].toString().includes('/api/v1/pantry') && c[1]?.method === 'PUT'
      );
      expect(putCall).toBeDefined();
      const payload = JSON.parse(putCall![1].body);
      expect(payload.items[0].raw_name).toBe('500 ml olive oil');
      expect(payload.items[0].canonical_ingredient_id).toBe(50);
    });
  });

  it('18. prevents adding duplicate canonical ingredient if already in the pantry', async () => {
    global.fetch = setupMockFetch({ pantryResponse: mockPopulatedPantryResponse }); // contains canonical 101
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-items-list')).toBeInTheDocument();
    });

    await user.type(screen.getByTestId('ingredient-search-input'), 'chick');
    await waitFor(() => {
      expect(screen.getByTestId('suggestion-item-101')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('suggestion-item-101'));

    await user.click(screen.getByTestId('add-ingredient-btn'));

    expect(await screen.findByTestId('add-ingredient-error')).toHaveTextContent(
      /'chicken breast' is already in your pantry inventory/i
    );
  });

  it('19. removes an ingredient via PUT /api/v1/pantry with updated filtered items', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-item-1')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('remove-item-1'));

    await waitFor(() => {
      const putCalls = mockFetch.mock.calls.filter(
        (c) => c[0].toString().includes('/api/v1/pantry') && c[1]?.method === 'PUT'
      );
      expect(putCalls.length).toBeGreaterThan(0);
      const lastPayload = JSON.parse(putCalls[putCalls.length - 1][1].body);
      // Item 1 removed, only item 2 remains
      expect(lastPayload.items).toHaveLength(1);
      expect(lastPayload.items[0].canonical_ingredient_id).toBe(10);
    });
  });

  it('20. clears all pantry items via PUT /api/v1/pantry with empty array', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('clear-all-pantry-btn')).toBeInTheDocument();
    });

    // First click asks confirmation
    await user.click(screen.getByTestId('clear-all-pantry-btn'));
    expect(screen.getByTestId('clear-all-pantry-btn')).toHaveTextContent(/Click again to confirm/i);

    // Second click executes clear
    await user.click(screen.getByTestId('clear-all-pantry-btn'));

    await waitFor(() => {
      const putCall = mockFetch.mock.calls.find(
        (c) => c[0].toString().includes('/api/v1/pantry') && c[1]?.method === 'PUT'
      );
      expect(putCall).toBeDefined();
      const payload = JSON.parse(putCall![1].body);
      expect(payload.items).toEqual([]);
    });
  });

  it('21. handles pantry update failure without corrupting or retaining unsaved UI state', async () => {
    const mockFetch = setupMockFetch({ updatePantryStatus: 500 });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-item-1')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('remove-item-1'));

    expect(await screen.findByText(/Failed to remove ingredient/i)).toBeInTheDocument();
    // Item 1 must still remain in UI
    expect(screen.getByTestId('pantry-item-1')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group D: Recipe Ingredient Matching
  // --------------------------------------------------------------------------

  it('22. renders matching engine section with staple exclusion and threshold controls', async () => {
    global.fetch = setupMockFetch();
    renderPantryPage();

    expect(screen.getByTestId('pantry-recipe-matcher-section')).toBeInTheDocument();
    expect(screen.getByTestId('matcher-heading')).toHaveTextContent('Recipe Overlap Matching Engine');
    expect(screen.getByTestId('staple-exclusion-checkbox')).toBeChecked();
    expect(screen.getByTestId('min-match-select')).toHaveValue('30');
    expect(screen.getByTestId('find-recipes-btn')).toBeInTheDocument();
  });

  it('23. disables Find Recipes button and warns when pantry is empty', async () => {
    global.fetch = setupMockFetch({ pantryResponse: mockEmptyPantryResponse });
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('empty-pantry-matcher-notice')).toBeInTheDocument();
    });

    expect(screen.getByTestId('find-recipes-btn')).toBeDisabled();
    expect(screen.getByTestId('empty-pantry-matcher-notice')).toHaveTextContent(
      /Add at least one ingredient to your pantry above/i
    );
  });

  it('24. triggers POST /api/v1/pantry/match and renders candidate recipe cards with scores', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('find-recipes-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('find-recipes-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('matches-grid')).toBeInTheDocument();
    });

    expect(screen.getByTestId('match-card-rcp_foodcom_5421')).toBeInTheDocument();
    expect(screen.getByTestId('match-score-rcp_foodcom_5421')).toHaveTextContent('67% Match');
    expect(screen.getByTestId('recipe-link-rcp_foodcom_5421')).toHaveTextContent(
      'Classic Rosemary Garlic Roasted Chicken'
    );
  });

  it('25. displays breakdown of matched vs missing ingredients for each candidate', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('find-recipes-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('find-recipes-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('matched-list-rcp_foodcom_5421')).toBeInTheDocument();
    });

    const matchedList = screen.getByTestId('matched-list-rcp_foodcom_5421');
    expect(within(matchedList).getByText('2 lbs chicken breast')).toBeInTheDocument();
    expect(within(matchedList).getByText('4 cloves garlic')).toBeInTheDocument();

    const missingList = screen.getByTestId('missing-list-rcp_foodcom_5421');
    expect(within(missingList).getByText('2 tbsp fresh rosemary')).toBeInTheDocument();
  });

  it('26. links candidate recipe card to recipe detail page /recipes/:recipeId', async () => {
    global.fetch = setupMockFetch();
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('find-recipes-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('find-recipes-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('view-recipe-btn-rcp_foodcom_5421')).toBeInTheDocument();
    });

    const link = screen.getByTestId('view-recipe-btn-rcp_foodcom_5421') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('/recipes/rcp_foodcom_5421');
  });

  it('27. updates staple exclusion parameter when checkbox is toggled', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('staple-exclusion-checkbox')).toBeInTheDocument();
    });

    await user.click(screen.getByTestId('staple-exclusion-checkbox')); // Uncheck
    expect(screen.getByTestId('staple-exclusion-checkbox')).not.toBeChecked();

    await user.click(screen.getByTestId('find-recipes-btn'));

    await waitFor(() => {
      const matchCall = mockFetch.mock.calls.find((c) =>
        c[0].toString().includes('/api/v1/pantry/match')
      );
      expect(matchCall).toBeDefined();
      const payload = JSON.parse(matchCall![1].body);
      expect(payload.exclude_pantry_staples).toBe(false);
    });
  });

  it('28. updates min_match_pct parameter when select option changes', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('min-match-select')).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByTestId('min-match-select'), '50');

    await user.click(screen.getByTestId('find-recipes-btn'));

    await waitFor(() => {
      const matchCall = mockFetch.mock.calls.find((c) =>
        c[0].toString().includes('/api/v1/pantry/match')
      );
      expect(matchCall).toBeDefined();
      const payload = JSON.parse(matchCall![1].body);
      expect(payload.min_match_pct).toBe(50);
    });
  });

  it('29. displays zero candidates state when no recipes meet threshold', async () => {
    const mockFetch = setupMockFetch({ matchResponse: mockEmptyMatchResponse });
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('find-recipes-btn')).not.toBeDisabled();
    });

    await user.selectOptions(screen.getByTestId('min-match-select'), '75');
    await user.click(screen.getByTestId('find-recipes-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('matcher-empty-results')).toBeInTheDocument();
    });

    expect(screen.getByText('No Matching Recipes Found')).toBeInTheDocument();
  });

  it('30. handles matching error with retry button', async () => {
    global.fetch = setupMockFetch({ matchStatus: 500 });
    const user = userEvent.setup();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('find-recipes-btn')).not.toBeDisabled();
    });

    await user.click(screen.getByTestId('find-recipes-btn'));

    expect(await screen.findByTestId('matcher-error')).toBeInTheDocument();
    expect(screen.getByTestId('matcher-retry-btn')).toBeInTheDocument();
  });

  // --------------------------------------------------------------------------
  // Group E: Architecture & Privacy Invariants
  // --------------------------------------------------------------------------

  it('31. strictly attaches X-Guest-Session-ID only to Planner Service requests', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-page')).toBeInTheDocument();
    });

    const plannerCalls = mockFetch.mock.calls.filter((c) =>
      c[0].toString().includes('/api/v1/pantry')
    );
    expect(plannerCalls.length).toBeGreaterThan(0);
    plannerCalls.forEach((call) => {
      expect(call[1].headers['X-Guest-Session-ID']).toBe(mockSessionId);
    });
  });

  it('32. strictly never attaches X-Guest-Session-ID to Recipe Service suggestion calls', async () => {
    const mockFetch = setupMockFetch();
    global.fetch = mockFetch;
    const user = userEvent.setup();
    renderPantryPage();

    await user.type(screen.getByTestId('ingredient-search-input'), 'chick');

    await waitFor(() => {
      expect(screen.getByTestId('suggestions-dropdown')).toBeInTheDocument();
    });

    const suggestionCall = mockFetch.mock.calls.find((c) =>
      c[0].toString().includes('/api/v1/ingredients/suggestions')
    );
    expect(suggestionCall).toBeDefined();
    expect(suggestionCall![1].headers['X-Guest-Session-ID']).toBeUndefined();
  });

  it('33. privacy invariant: zero biometric information or user identity tokens collected or saved', async () => {
    global.fetch = setupMockFetch();
    renderPantryPage();

    await waitFor(() => {
      expect(screen.getByTestId('pantry-page')).toBeInTheDocument();
    });

    // Check localStorage contains only the anonymous guest session and theme
    const storedKeys = Object.keys(localStorage);
    expect(storedKeys.filter((k) => k.includes('biometric') || k.includes('user_id'))).toHaveLength(0);
  });
});

