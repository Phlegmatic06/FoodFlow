/**
 * Recipe & Ingredient Service Client (Port 8002)
 * Conforms to contracts/openapi/recipe-service.yaml
 * Strictly does NOT attach or forward X-Guest-Session-ID.
 */

import { API_CONFIG } from './config';
import { httpClient, RequestOptions } from './http';
import { ServiceHealthStatus, ServiceReadinessStatus } from './types/common';
import {
  CanonicalIngredientDetail,
  IngredientSuggestion,
  NormalizedIngredientResult,
  PaginatedRecipeSummary,
  RecipeDetail,
  RecipeSearchParams,
} from './types/recipe';

export class RecipeServiceClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_CONFIG.recipeServiceUrl) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  // Health and Readiness
  async getHealth(options?: RequestOptions): Promise<ServiceHealthStatus> {
    return httpClient.get<ServiceHealthStatus>(`${this.baseUrl}/api/v1/health`, options);
  }

  async getLiveness(options?: RequestOptions): Promise<ServiceHealthStatus> {
    return httpClient.get<ServiceHealthStatus>(`${this.baseUrl}/api/v1/health/liveness`, options);
  }

  async getReadiness(options?: RequestOptions): Promise<ServiceReadinessStatus> {
    return httpClient.get<ServiceReadinessStatus>(`${this.baseUrl}/api/v1/health/readiness`, options);
  }

  // Recipe Discovery
  async searchRecipes(
    params: RecipeSearchParams = {},
    options?: RequestOptions
  ): Promise<PaginatedRecipeSummary> {
    const queryParams: Record<string, string | number | boolean | undefined> = {
      q: params.q,
      cuisine: params.cuisine,
      tag: params.tag,
      diet: params.diet,
      max_time: params.max_time,
      source_dataset: params.source_dataset,
      sort: params.sort,
      page: params.page ?? 1,
      limit: params.limit ?? 24,
    };

    return httpClient.get<PaginatedRecipeSummary>(`${this.baseUrl}/api/v1/recipes/search`, {
      ...options,
      params: queryParams,
    });
  }

  async getRecipe(recipeId: string, options?: RequestOptions): Promise<RecipeDetail> {
    return httpClient.get<RecipeDetail>(
      `${this.baseUrl}/api/v1/recipes/${encodeURIComponent(recipeId)}`,
      options
    );
  }

  // Ingredient Normalization & Taxonomy
  async getIngredientSuggestions(
    query: string,
    limit: number = 10,
    options?: RequestOptions
  ): Promise<IngredientSuggestion[]> {
    return httpClient.get<IngredientSuggestion[]>(
      `${this.baseUrl}/api/v1/ingredients/suggestions`,
      {
        ...options,
        params: { q: query, limit },
      }
    );
  }

  async searchIngredients(
    query: string,
    limit: number = 20,
    options?: RequestOptions
  ): Promise<{ data: CanonicalIngredientDetail[] }> {
    return httpClient.get(`${this.baseUrl}/api/v1/ingredients/search`, {
      ...options,
      params: { q: query, limit },
    });
  }

  async normalizeIngredients(
    ingredients: string[],
    options?: RequestOptions
  ): Promise<{ results: NormalizedIngredientResult[] }> {
    return httpClient.post<{ results: NormalizedIngredientResult[] }>(
      `${this.baseUrl}/api/v1/ingredients/normalize`,
      { ingredients },
      options
    );
  }

  async getCanonicalIngredient(
    canonicalId: number,
    options?: RequestOptions
  ): Promise<CanonicalIngredientDetail> {
    return httpClient.get<CanonicalIngredientDetail>(
      `${this.baseUrl}/api/v1/ingredients/${canonicalId}`,
      options
    );
  }
}

export const recipeClient = new RecipeServiceClient();

