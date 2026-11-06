import { createBrowserRouter, RouteObject } from 'react-router-dom';
import { Layout } from './components/Layout';
import { HomePage } from './pages/HomePage';
import { RecipeDiscoveryPage } from './pages/RecipeDiscoveryPage';
import { RecipeDetailPage } from './pages/RecipeDetailPage';
import { PantryPage } from './pages/PantryPage';
import { MealPlannerPage } from './pages/MealPlannerPage';
import { NutritionPage } from './pages/NutritionPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const routes: RouteObject[] = [
  {
    path: '/',
    element: <Layout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'recipes',
        element: <RecipeDiscoveryPage />,
      },
      {
        path: 'recipes/:recipeId',
        element: <RecipeDetailPage />,
      },
      {
        path: 'pantry',
        element: <PantryPage />,
      },
      {
        path: 'meal-plans',
        element: <MealPlannerPage />,
      },
      {
        path: 'nutrition',
        element: <NutritionPage />,
      },
      {
        path: '*',
        element: <NotFoundPage />,
      },
    ],
  },
];

export const router = createBrowserRouter(routes);

