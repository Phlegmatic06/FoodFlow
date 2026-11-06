import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { routes } from '../router';
import { ThemeProvider } from '../theme/ThemeContext';
import { PaginatedRecipeSummary, RecipeSummary } from '../api/types/recipe';

const mockFoodComRecipe: RecipeSummary = {
  id: 'rcp_foodcom_5421',
  source_dataset: 'food_com',
  source_id: '5421',
  title: 'Classic Rosemary Garlic Roasted Chicken',
  description: 'Succulent whole roasted chicken infused with fresh rosemary and garlic.',
  prep_time_minutes: null,
  cook_time_minutes: null,
  total_time_minutes: 75,
  servings: null,
  cuisine: 'Mediterranean',
  source_url: 'https://www.food.com/recipe/rosemary-chicken-5421',
  rating_average: 4.75,
  rating_count: 28,
  tag_preview: ['dinner', 'chicken', 'roast', 'gluten-free'],
};

const mockRecipeNLGRecipe: RecipeSummary = {
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
  rating_average: null,
  rating_count: 0,
  tag_preview: ['bread', 'baking'],
};

function createMockSearchResponse(
  data: RecipeSummary[] = [mockFoodComRecipe, mockRecipeNLGRecipe],
  page: number = 1,
  limit: number = 24,
  total_items: number = 2
): PaginatedRecipeSummary {
  return {
    data,
    pagination: {
      page,
      limit,
      total_items,
      total_pages: Math.ceil(total_items / limit),
    },
  };
}

function renderDiscovery(initialEntries: string[] = ['/recipes']) {
  const router = createMemoryRouter(routes, {
    initialEntries,
  });

  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

describe('Recipe Discovery, Search, Filtering & Sorting (Step 05.2)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  // 1. Initial recipe discovery loading
  it('1. displays loading state on initial discovery mount', async () => {
    // Delay resolution
    global.fetch = vi.fn().mockImplementation(() => new Promise(() => {}));

    renderDiscovery(['/recipes']);

    expect(screen.getByLabelText(/loading recipes/i)).toBeInTheDocument();
    expect(screen.getByText(/querying 50,000 recipes across postgresql/i)).toBeInTheDocument();
  });

  // 2. Successful rendering of real-shaped API response data
  it('2. renders real-shaped recipe results successfully', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse(),
    });

    renderDiscovery(['/recipes']);

    expect(await screen.findByText('Classic Rosemary Garlic Roasted Chicken')).toBeInTheDocument();
    expect(screen.getByText('Rustic Herb Flatbread')).toBeInTheDocument();
    expect(screen.getByText('Food.com')).toBeInTheDocument();
    expect(screen.getByText('RecipeNLG')).toBeInTheDocument();
    expect(screen.getByText(/Found/i)).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  // 3. Search submission
  it('3. submits search query on button click or Enter key', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockFoodComRecipe], 1, 24, 1),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const searchInput = screen.getByRole('searchbox', { name: /search recipes/i });
    await user.type(searchInput, 'rosemary chicken');

    const submitBtn = screen.getByRole('button', { name: /submit recipe search/i });
    await user.click(submitBtn);

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).toContain('q=rosemary+chicken');
    });
  });

  // 4. Search clearing
  it('4. clears search query and refreshes results', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse(),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes?q=rosemary']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const clearBtn = screen.getByRole('button', { name: /clear search query/i });
    await user.click(clearBtn);

    const searchInput = screen.getByRole('searchbox', { name: /search recipes/i }) as HTMLInputElement;
    expect(searchInput.value).toBe('');

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).not.toContain('q=rosemary');
    });
  });

  // 5. Filter application
  it('6. applies cuisine filter and passes to API', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockFoodComRecipe], 1, 24, 1),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const cuisineSelect = screen.getByLabelText(/cuisine/i);
    await user.selectOptions(cuisineSelect, 'Italian');

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).toContain('cuisine=Italian');
    });

    expect(screen.getByRole('button', { name: /remove cuisine filter: italian/i })).toBeInTheDocument();
  });

  // 7. Multiple simultaneous filters
  it('7. applies multiple filters simultaneously', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockFoodComRecipe], 1, 24, 1),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    await user.selectOptions(screen.getByLabelText(/cuisine/i), 'Italian');
    await user.selectOptions(screen.getByLabelText(/dietary category/i), 'vegetarian');
    await user.selectOptions(screen.getByLabelText(/max total time/i), '45');
    await user.selectOptions(screen.getByLabelText(/source dataset/i), 'food_com');

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).toContain('cuisine=Italian');
      expect(lastCallUrl).toContain('diet=vegetarian');
      expect(lastCallUrl).toContain('max_time=45');
      expect(lastCallUrl).toContain('source_dataset=food_com');
    });
  });

  // 8. Removing an active filter
  it('8. removes individual active filter when clicking chip', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse(),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes?cuisine=Italian&diet=vegan']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const removeCuisineChip = screen.getByRole('button', { name: /remove cuisine filter: italian/i });
    await user.click(removeCuisineChip);

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).not.toContain('cuisine=Italian');
      expect(lastCallUrl).toContain('diet=vegan');
    });
  });

  // 9. Clearing all filters
  it('9. clears all filters on Clear All button click', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse(),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes?cuisine=Italian&diet=vegan&max_time=30']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const clearAllBtn = screen.getByRole('button', { name: /clear all active filters/i });
    await user.click(clearAllBtn);

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).not.toContain('cuisine=');
      expect(lastCallUrl).not.toContain('diet=');
      expect(lastCallUrl).not.toContain('max_time=');
    });
  });

  // 10. Sorting
  it('10. changes sort order and re-queries backend', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse(),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const sortSelect = screen.getByLabelText(/sort recipes by/i);
    await user.selectOptions(sortSelect, 'rating');

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).toContain('sort=rating');
    });
  });

  // 11. Pagination
  it('11. paginates to next page on click', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockFoodComRecipe], 1, 24, 50),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const nextBtn = screen.getByRole('button', { name: /next page/i });
    await user.click(nextBtn);

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).toContain('page=2');
    });
  });

  // 12. Pagination reset after changing filters or query
  it('12. resets page to 1 when changing filters or search terms', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockFoodComRecipe], 2, 24, 50),
    });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes?page=2']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const searchInput = screen.getByRole('searchbox', { name: /search recipes/i });
    await user.type(searchInput, 'pasta');
    await user.click(screen.getByRole('button', { name: /submit recipe search/i }));

    await waitFor(() => {
      const calls = mockFetch.mock.calls;
      const lastCallUrl = calls[calls.length - 1][0];
      expect(lastCallUrl).toContain('q=pasta');
      expect(lastCallUrl).toContain('page=1');
    });
  });

  // 13. Empty results
  it('13. displays empty state when zero recipes match criteria', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([], 1, 24, 0),
    });

    renderDiscovery(['/recipes?q=nonexistent+dish']);

    expect(await screen.findByRole('heading', { level: 3, name: /no matching recipes found/i })).toBeInTheDocument();
    expect(screen.getByText(/zero results/i)).toBeInTheDocument();
  });

  // 14. API errors and retry
  it('14. displays error state on failure and retries successfully', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: async () => ({
          error: { code: 'DATABASE_ERROR', message: 'Connection to PostgreSQL failed' },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => createMockSearchResponse(),
      });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes']);

    expect(await screen.findByText(/connection to postgresql failed/i)).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /try again/i });
    await user.click(retryBtn);

    expect(await screen.findByText('Classic Rosemary Garlic Roasted Chicken')).toBeInTheDocument();
  });

  // 15. Missing rating and missing time display
  it('15. renders honest "unavailable" indicators for missing rating and time', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockRecipeNLGRecipe], 1, 24, 1),
    });

    renderDiscovery(['/recipes']);

    await screen.findByText('Rustic Herb Flatbread');

    // Missing rating & time must say "Rating unavailable" and "Time unavailable", NOT "0 stars" or "0 mins"
    expect(screen.getByTestId('recipe-rating')).toHaveTextContent('Rating unavailable');
    expect(screen.getByTestId('recipe-time')).toHaveTextContent('Time unavailable');
    expect(screen.getByTestId('recipe-rating')).not.toHaveTextContent('0');
    expect(screen.getByTestId('recipe-time')).not.toHaveTextContent('0 mins');
  });

  // 16. Missing nutrition display
  it('16. does not fabricate nutrition data on recipe summaries', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockRecipeNLGRecipe], 1, 24, 1),
    });

    renderDiscovery(['/recipes']);

    await screen.findByText('Rustic Herb Flatbread');
    // Ensure no synthetic calorie/macro badges exist
    expect(screen.queryByText(/kcal/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/protein/i)).not.toBeInTheDocument();
  });

  // 17. Navigation to a recipe detail URL
  it('17. provides link pointing to recipe detail route', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockFoodComRecipe], 1, 24, 1),
    });

    renderDiscovery(['/recipes']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    const detailLinks = screen.getAllByRole('link', { name: /classic rosemary garlic roasted chicken|view recipe/i });
    expect(detailLinks[0]).toHaveAttribute('href', '/recipes/rcp_foodcom_5421');
  });

  // 18. Prevention of stale search responses
  it('18. prevents stale slow responses from overwriting newer query results', async () => {
    let slowResolve: (val: any) => void;
    const slowPromise = new Promise((resolve) => {
      slowResolve = resolve;
    });

    const mockFetch = vi
      .fn()
      // First request (slow)
      .mockImplementationOnce(() => slowPromise)
      // Second request (fast)
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => createMockSearchResponse([mockFoodComRecipe], 1, 24, 1),
      });
    global.fetch = mockFetch;

    const user = userEvent.setup();
    renderDiscovery(['/recipes']);

    // Quickly submit new query
    const searchInput = screen.getByRole('searchbox', { name: /search recipes/i });
    await user.type(searchInput, 'fast query');
    await user.click(screen.getByRole('button', { name: /submit recipe search/i }));

    // Fast response resolves
    expect(await screen.findByText('Classic Rosemary Garlic Roasted Chicken')).toBeInTheDocument();

    // Now resolve old slow query with RecipeNLG
    slowResolve!({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockRecipeNLGRecipe], 1, 24, 1),
    });

    // Verify fast query result is NOT overwritten by stale response
    expect(screen.getByText('Classic Rosemary Garlic Roasted Chicken')).toBeInTheDocument();
  });

  // 19. URL state restoration
  it('19. restores search, filter, and sort state from URL query parameters', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => createMockSearchResponse([mockFoodComRecipe], 2, 24, 50),
    });
    global.fetch = mockFetch;

    renderDiscovery(['/recipes?q=chicken&cuisine=Italian&diet=gluten-free&max_time=60&source_dataset=food_com&sort=rating&page=2']);

    await screen.findByText('Classic Rosemary Garlic Roasted Chicken');

    // Input populated
    const searchInput = screen.getByRole('searchbox', { name: /search recipes/i }) as HTMLInputElement;
    expect(searchInput.value).toBe('chicken');

    // Filters populated
    const cuisineSelect = screen.getByRole('combobox', { name: /^cuisine$/i }) as HTMLSelectElement;
    expect(cuisineSelect.value).toBe('Italian');

    const dietSelect = screen.getByRole('combobox', { name: /^dietary category$/i }) as HTMLSelectElement;
    expect(dietSelect.value).toBe('gluten-free');

    const timeSelect = screen.getByRole('combobox', { name: /^max total time$/i }) as HTMLSelectElement;
    expect(timeSelect.value).toBe('60');

    const datasetSelect = screen.getByRole('combobox', { name: /^source dataset$/i }) as HTMLSelectElement;
    expect(datasetSelect.value).toBe('food_com');

    // Sort populated
    const sortSelect = screen.getByRole('combobox', { name: /^sort recipes by$/i }) as HTMLSelectElement;
    expect(sortSelect.value).toBe('rating');

    // API called with restored params
    const [initialUrl] = mockFetch.mock.calls[0];
    expect(initialUrl).toContain('q=chicken');
    expect(initialUrl).toContain('cuisine=Italian');
    expect(initialUrl).toContain('diet=gluten-free');
    expect(initialUrl).toContain('max_time=60');
    expect(initialUrl).toContain('source_dataset=food_com');
    expect(initialUrl).toContain('sort=rating');
    expect(initialUrl).toContain('page=2');
  });
});
