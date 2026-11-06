/**
 * Profile & Nutrition Service Client (Port 8001)
 * Conforms to contracts/openapi/profile-service.yaml
 * Strictly does NOT attach or forward X-Guest-Session-ID.
 */

import { API_CONFIG } from './config';
import { httpClient, RequestOptions } from './http';
import { ServiceHealthStatus, ServiceReadinessStatus } from './types/common';
import {
  BiometricsCalculationRequest,
  BiometricsCalculationResponse,
  CachedRecipeNutrition,
  PaginatedUSDAFoodSummary,
  RecipeNutritionEstimateRequest,
  RecipeNutritionEstimateResponse,
  USDAFoodDetail,
  UserTargetSummary,
} from './types/profile';

export class ProfileServiceClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_CONFIG.profileServiceUrl) {
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

  // Biometrics & Nutritional Targets
  async calculateBiometrics(
    data: BiometricsCalculationRequest,
    options?: RequestOptions
  ): Promise<BiometricsCalculationResponse> {
    return httpClient.post<BiometricsCalculationResponse>(
      `${this.baseUrl}/api/v1/biometrics/calculate`,
      data,
      options
    );
  }

  async getTargets(options?: RequestOptions): Promise<UserTargetSummary> {
    return httpClient.get<UserTargetSummary>(`${this.baseUrl}/api/v1/profile/targets`, options);
  }

  // USDA Foods & Nutrition
  async searchFoods(
    query: string,
    limit: number = 24,
    page: number = 1,
    options?: RequestOptions
  ): Promise<PaginatedUSDAFoodSummary> {
    return httpClient.get<PaginatedUSDAFoodSummary>(`${this.baseUrl}/api/v1/nutrition/foods/search`, {
      ...options,
      params: { q: query, limit, page },
    });
  }

  async getFoodDetail(fdcId: number, options?: RequestOptions): Promise<USDAFoodDetail> {
    return httpClient.get<USDAFoodDetail>(`${this.baseUrl}/api/v1/nutrition/foods/${fdcId}`, options);
  }

  async estimateRecipeNutrition(
    data: RecipeNutritionEstimateRequest,
    options?: RequestOptions
  ): Promise<RecipeNutritionEstimateResponse> {
    return httpClient.post<RecipeNutritionEstimateResponse>(
      `${this.baseUrl}/api/v1/nutrition/recipes/estimate`,
      data,
      options
    );
  }

  async getRecipeNutrition(
    recipeId: string,
    options?: RequestOptions
  ): Promise<CachedRecipeNutrition> {
    return httpClient.get<CachedRecipeNutrition>(
      `${this.baseUrl}/api/v1/nutrition/recipes/${encodeURIComponent(recipeId)}`,
      options
    );
  }
}

export const profileClient = new ProfileServiceClient();

