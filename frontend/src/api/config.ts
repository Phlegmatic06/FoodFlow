/**
 * FoodFlow API Service Configuration
 * Provides base URLs and default timeouts for the three microservices.
 */

export interface ApiConfig {
  profileServiceUrl: string;
  recipeServiceUrl: string;
  plannerServiceUrl: string;
  defaultTimeoutMs: number;
}

export const API_CONFIG: ApiConfig = {
  profileServiceUrl:
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_PROFILE_SERVICE_URL) ||
    'http://localhost:8001',
  recipeServiceUrl:
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_RECIPE_SERVICE_URL) ||
    'http://localhost:8002',
  plannerServiceUrl:
    (typeof import.meta !== 'undefined' && import.meta.env?.VITE_PLANNER_SERVICE_URL) ||
    'http://localhost:8003',
  defaultTimeoutMs: 10000,
};

