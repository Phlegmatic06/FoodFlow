/**
 * Recommendation & Meal Planner Service Client (Port 8003)
 * Conforms to contracts/openapi/planner-service.yaml
 * Exclusively manages and attaches X-Guest-Session-ID header for guest sessions.
 */

import { API_CONFIG } from './config';
import { httpClient, RequestOptions } from './http';
import { ServiceHealthStatus, ServiceReadinessStatus } from './types/common';
import {
  GeneratedMealPlanResponse,
  GenerateMealPlanRequest,
  GuestSession,
  MealPlanDetail,
  PantryInventoryResponse,
  PantryMatchRequest,
  PantryMatchResponse,
  SavedMealPlanSummary,
  SaveMealPlanRequest,
  ShoppingListItem,
  ShoppingListResponse,
  SlotCookingProgressUpdate,
  UpdatePantryItemInput,
  UpdateProgressResponse,
} from './types/planner';

export class PlannerServiceClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string = API_CONFIG.plannerServiceUrl) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
  }

  public getBaseUrl(): string {
    return this.baseUrl;
  }

  private withGuestSession(sessionId?: string, options?: RequestOptions): RequestOptions {
    if (!sessionId) return options || {};
    return {
      ...options,
      customHeaders: {
        ...(options?.customHeaders || {}),
        'X-Guest-Session-ID': sessionId,
      },
    };
  }

  // Health and Readiness
  async getHealth(options?: RequestOptions): Promise<ServiceHealthStatus> {
    return httpClient.get<ServiceHealthStatus>(`${this.baseUrl}/health`, options);
  }

  async getLiveness(options?: RequestOptions): Promise<ServiceHealthStatus> {
    return httpClient.get<ServiceHealthStatus>(`${this.baseUrl}/health`, options);
  }

  async getReadiness(options?: RequestOptions): Promise<ServiceReadinessStatus> {
    return httpClient.get<ServiceReadinessStatus>(`${this.baseUrl}/health`, options);
  }

  // Guest Sessions
  async createGuestSession(options?: RequestOptions): Promise<GuestSession> {
    return httpClient.post<GuestSession>(
      `${this.baseUrl}/api/v1/guest-sessions`,
      {},
      options
    );
  }

  async getGuestSession(sessionId: string, options?: RequestOptions): Promise<GuestSession> {
    return httpClient.get<GuestSession>(
      `${this.baseUrl}/api/v1/guest-sessions/${encodeURIComponent(sessionId)}`,
      options
    );
  }

  // Pantry Management
  async getPantry(
    sessionId: string,
    options?: RequestOptions
  ): Promise<PantryInventoryResponse> {
    return httpClient.get<PantryInventoryResponse>(
      `${this.baseUrl}/api/v1/pantry`,
      this.withGuestSession(sessionId, options)
    );
  }

  async updatePantry(
    items: UpdatePantryItemInput[],
    sessionId: string,
    options?: RequestOptions
  ): Promise<PantryInventoryResponse> {
    return httpClient.put<PantryInventoryResponse>(
      `${this.baseUrl}/api/v1/pantry`,
      { items },
      this.withGuestSession(sessionId, options)
    );
  }

  async matchPantry(
    request: PantryMatchRequest,
    sessionId?: string,
    options?: RequestOptions
  ): Promise<PantryMatchResponse> {
    return httpClient.post<PantryMatchResponse>(
      `${this.baseUrl}/api/v1/pantry/match`,
      request,
      this.withGuestSession(sessionId, options)
    );
  }

  // Meal Planning: Generation
  async generateMealPlan(
    request: GenerateMealPlanRequest,
    options?: RequestOptions
  ): Promise<GeneratedMealPlanResponse> {
    return httpClient.post<GeneratedMealPlanResponse>(
      `${this.baseUrl}/api/v1/meal-plans/generate`,
      request,
      options
    );
  }

  // Backward-compatibility alias
  async proposeMealPlan(
    request: any,
    options?: RequestOptions
  ): Promise<any> {
    return this.generateMealPlan(request, options);
  }

  // Meal Planning: Persistence & Retrieval
  async saveMealPlan(
    plan: SaveMealPlanRequest,
    sessionId: string,
    options?: RequestOptions
  ): Promise<SavedMealPlanSummary> {
    const payload: SaveMealPlanRequest = {
      name: plan.name || plan.title || 'Weekly Meal Plan',
      days: plan.days,
      target_calories_kcal: plan.target_calories_kcal ?? plan.target_calories_daily ?? null,
      slots: (plan.slots || []).map((s: any) => ({
        day_index: s.day_index ?? s.day_number ?? 0,
        slot_type: s.slot_type ?? s.meal_type ?? 'dinner',
        recipe_id: s.recipe_id,
        recipe_title: s.recipe_title || 'Recipe',
      })),
    };
    return httpClient.post<SavedMealPlanSummary>(
      `${this.baseUrl}/api/v1/meal-plans`,
      payload,
      this.withGuestSession(sessionId, options)
    );
  }

  async getMealPlan(
    planId: string,
    sessionId: string,
    options?: RequestOptions
  ): Promise<MealPlanDetail> {
    return httpClient.get<MealPlanDetail>(
      `${this.baseUrl}/api/v1/meal-plans/${encodeURIComponent(planId)}`,
      this.withGuestSession(sessionId, options)
    );
  }

  async updateMealPlan(
    planId: string,
    plan: SaveMealPlanRequest,
    sessionId: string,
    options?: RequestOptions
  ): Promise<MealPlanDetail> {
    const payload: SaveMealPlanRequest = {
      name: plan.name || plan.title || 'Weekly Meal Plan',
      days: plan.days,
      target_calories_kcal: plan.target_calories_kcal ?? plan.target_calories_daily ?? null,
      slots: (plan.slots || []).map((s: any) => ({
        day_index: s.day_index ?? s.day_number ?? 0,
        slot_type: s.slot_type ?? s.meal_type ?? 'dinner',
        recipe_id: s.recipe_id,
        recipe_title: s.recipe_title || 'Recipe',
      })),
    };
    return httpClient.put<MealPlanDetail>(
      `${this.baseUrl}/api/v1/meal-plans/${encodeURIComponent(planId)}`,
      payload,
      this.withGuestSession(sessionId, options)
    );
  }

  async deleteMealPlan(
    planId: string,
    sessionId: string,
    options?: RequestOptions
  ): Promise<void> {
    return httpClient.del<void>(
      `${this.baseUrl}/api/v1/meal-plans/${encodeURIComponent(planId)}`,
      this.withGuestSession(sessionId, options)
    );
  }

  // Cooking Progress
  async updateCookingProgress(
    planId: string,
    updates: SlotCookingProgressUpdate[],
    sessionId: string,
    options?: RequestOptions
  ): Promise<UpdateProgressResponse> {
    return httpClient.patch<UpdateProgressResponse>(
      `${this.baseUrl}/api/v1/meal-plans/${encodeURIComponent(planId)}/progress`,
      { updates },
      this.withGuestSession(sessionId, options)
    );
  }

  // Shopping List
  async getShoppingList(
    planId: string,
    sessionId: string,
    options?: RequestOptions
  ): Promise<ShoppingListResponse> {
    return httpClient.get<ShoppingListResponse>(
      `${this.baseUrl}/api/v1/meal-plans/${encodeURIComponent(planId)}/shopping-list`,
      this.withGuestSession(sessionId, options)
    );
  }

  async updateShoppingListItem(
    planId: string,
    itemId: number,
    checked: boolean,
    sessionId: string,
    options?: RequestOptions
  ): Promise<ShoppingListItem> {
    return httpClient.patch<ShoppingListItem>(
      `${this.baseUrl}/api/v1/meal-plans/${encodeURIComponent(planId)}/shopping-list/items/${encodeURIComponent(itemId)}`,
      { checked },
      this.withGuestSession(sessionId, options)
    );
  }
}

export const plannerClient = new PlannerServiceClient();
