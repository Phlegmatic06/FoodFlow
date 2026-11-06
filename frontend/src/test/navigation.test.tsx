import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { routes } from '../router';
import { ThemeProvider } from '../theme/ThemeContext';

function renderAppWithRoute(initialEntries: string[] = ['/']) {
  const router = createMemoryRouter(routes, {
    initialEntries,
  });

  return render(
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  );
}

describe('App Shell & Navigation Routing', () => {
  it('renders home page with editorial masthead and skip link', () => {
    renderAppWithRoute(['/']);

    // Skip Link
    const skipLink = screen.getByRole('link', { name: /skip to main content/i });
    expect(skipLink).toBeInTheDocument();
    expect(skipLink).toHaveAttribute('href', '#main-content');

    // Header Brand
    expect(screen.getByText('FoodFlow')).toBeInTheDocument();
    expect(screen.getByText('Nutritional Planning & Discovery')).toBeInTheDocument();

    // Home Hero Heading
    expect(
      screen.getByRole('heading', { level: 1, name: /computational gastronomy & nutritional science/i })
    ).toBeInTheDocument();

    // Microservice indicators in footer
    expect(screen.getAllByText(/profile & nutrition/i).length).toBeGreaterThan(0);
    expect(screen.getByText(':8001')).toBeInTheDocument();
    expect(screen.getAllByText(/recipe & ingredient/i).length).toBeGreaterThan(0);
    expect(screen.getByText(':8002')).toBeInTheDocument();
    expect(screen.getAllByText(/meal planner/i).length).toBeGreaterThan(0);
    expect(screen.getByText(':8003')).toBeInTheDocument();
  });

  it('navigates to recipes page when Recipes link is clicked', async () => {
    const user = userEvent.setup();
    renderAppWithRoute(['/']);

    const recipesNav = screen.getAllByRole('link', { name: /^recipes$/i })[0];
    await user.click(recipesNav);

    expect(
      await screen.findByRole('heading', { level: 1, name: /recipe discovery & culinary search/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/50,000 verified culinary preparations/i)).toBeInTheDocument();
  });

  it('navigates to pantry page when Pantry link is clicked', async () => {
    const user = userEvent.setup();
    renderAppWithRoute(['/']);

    const pantryNav = screen.getAllByRole('link', { name: /^pantry$/i })[0];
    await user.click(pantryNav);

    expect(
      await screen.findByRole('heading', { level: 1, name: /pantry inventory & ingredient matching/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/zero-waste matching engine/i)).toBeInTheDocument();
  });

  it('navigates to meal planner page when Meal Planner link is clicked', async () => {
    const user = userEvent.setup();
    renderAppWithRoute(['/']);

    const plannerNav = screen.getAllByRole('link', { name: /^meal planner$/i })[0];
    await user.click(plannerNav);

    expect(
      await screen.findByRole('heading', { level: 1, name: /weekly meal planning & macro optimization/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/AMDR Macronutrient Grounding/i)).toBeInTheDocument();
  });

  it('navigates to nutrition page when Nutrition link is clicked', async () => {
    const user = userEvent.setup();
    renderAppWithRoute(['/']);

    const nutritionNav = screen.getAllByRole('link', { name: /^nutrition$/i })[0];
    await user.click(nutritionNav);

    expect(
      await screen.findByRole('heading', { level: 1, name: /biometric profiling & usda nutritional science/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/Mifflin-St Jeor/i)).toBeInTheDocument();
  });

  it('renders recipe detail page for dynamic route /recipes/:recipeId', async () => {
    const originalFetch = global.fetch;
    global.fetch = vi.fn().mockImplementation((url: string | URL) => {
      const urlStr = url.toString();
      if (urlStr.includes('/api/v1/recipes/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            id: 'rcp_foodcom_5421',
            source_dataset: 'food_com',
            source_id: '5421',
            title: 'Classic Rosemary Garlic Roasted Chicken',
            ingredients: [],
            instructions: [],
            tags: [],
            rating_average: 4.5,
            rating_count: 10,
            total_time_minutes: 60,
          }),
        });
      }
      return Promise.resolve({
        ok: false,
        status: 404,
        json: async () => ({ error: { message: 'Not cached' } }),
      });
    });

    try {
      renderAppWithRoute(['/recipes/rcp_foodcom_5421']);

      expect(
        await screen.findByRole('heading', { level: 1, name: /classic rosemary garlic roasted chicken/i })
      ).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /back to recipe discovery/i })).toBeInTheDocument();
    } finally {
      global.fetch = originalFetch;
    }
  });

  it('renders 404 not found page for unregistered routes', () => {
    renderAppWithRoute(['/unknown-path-does-not-exist']);

    expect(
      screen.getByRole('heading', { level: 1, name: /page not found/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/HTTP 404/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /return to home/i })).toBeInTheDocument();
  });
});
