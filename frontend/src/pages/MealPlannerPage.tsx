import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  CookingStatus,
  MealPlanDetail,
  SaveMealPlanRequest,
  ShoppingListResponse,
} from '../api/types/planner';
import { plannerClient } from '../api/plannerClient';
import {
  getOrCreateGuestSession,
  recoverExpiredGuestSession,
} from '../utils/guestSession';
import { MealPlanGenerator } from '../components/planner/MealPlanGenerator';
import { WeeklyOverviewGrid } from '../components/planner/WeeklyOverviewGrid';
import { ShoppingListSection } from '../components/planner/ShoppingListSection';
import { MealPlanNutritionSummary } from '../components/planner/MealPlanNutritionSummary';

export const ACTIVE_PLAN_STORAGE_KEY = 'foodflow_active_plan_id';

type TabView = 'schedule' | 'shopping' | 'nutrition';

export const MealPlannerPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activePlanId, setActivePlanId] = useState<string | null>(() => {
    return searchParams.get('plan_id') || localStorage.getItem(ACTIVE_PLAN_STORAGE_KEY) || null;
  });

  const [activeTab, setActiveTab] = useState<TabView>('schedule');
  const [showGenerator, setShowGenerator] = useState<boolean>(false);

  // Data states
  const [plan, setPlan] = useState<MealPlanDetail | null>(null);
  const [shoppingList, setShoppingList] = useState<ShoppingListResponse | null>(null);

  // Status states
  const [isLoadingPlan, setIsLoadingPlan] = useState<boolean>(false);
  const [planError, setPlanError] = useState<string | null>(null);

  const [isLoadingShopping, setIsLoadingShopping] = useState<boolean>(false);
  const [shoppingError, setShoppingError] = useState<string | null>(null);

  const [isMutating, setIsMutating] = useState<boolean>(false);

  // 1. Initialize guest session once on mount
  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const sid = await getOrCreateGuestSession();
        if (isMounted) setSessionId(sid);
      } catch (err: unknown) {
        if (isMounted) {
          setPlanError(
            err instanceof Error ? err.message : 'Failed to initialize anonymous guest session.'
          );
        }
      }
    })();
    return () => {
      isMounted = false;
    };
  }, []);

  // 2. Fetch saved meal plan by ID
  const fetchMealPlan = useCallback(
    async (planIdToFetch: string, sessionToken?: string) => {
      setIsLoadingPlan(true);
      setPlanError(null);

      const activeSession = sessionToken || sessionId || (await getOrCreateGuestSession());
      setSessionId(activeSession);

      try {
        const fetchedPlan = await plannerClient.getMealPlan(planIdToFetch, activeSession);
        setPlan(fetchedPlan);
        localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, fetchedPlan.id);
        setActivePlanId(fetchedPlan.id);
      } catch (err: unknown) {
        const isExpired =
          (err as { statusCode?: number })?.statusCode === 401 ||
          (err as { status?: number })?.status === 401;

        if (isExpired) {
          const freshSession = await recoverExpiredGuestSession();
          setSessionId(freshSession);
          try {
            const fetchedPlan = await plannerClient.getMealPlan(planIdToFetch, freshSession);
            setPlan(fetchedPlan);
            localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, fetchedPlan.id);
            setActivePlanId(fetchedPlan.id);
            return;
          } catch {
            // Failed after recovery
          }
        }

        const is404 =
          (err as { statusCode?: number })?.statusCode === 404 ||
          (err as { status?: number })?.status === 404;

        if (is404) {
          // Stale or deleted plan ID
          localStorage.removeItem(ACTIVE_PLAN_STORAGE_KEY);
          setActivePlanId(null);
          setPlan(null);
        } else {
          setPlanError(
            err instanceof Error ? err.message : 'Failed to retrieve saved meal plan schedule.'
          );
        }
      } finally {
        setIsLoadingPlan(false);
      }
    },
    [sessionId]
  );

  // 3. Fetch consolidated shopping list for plan
  const fetchShoppingList = useCallback(
    async (planIdToFetch: string, sessionToken?: string) => {
      setIsLoadingShopping(true);
      setShoppingError(null);

      const activeSession = sessionToken || sessionId || (await getOrCreateGuestSession());
      setSessionId(activeSession);

      try {
        const fetchedList = await plannerClient.getShoppingList(planIdToFetch, activeSession);
        setShoppingList(fetchedList);
      } catch (err: unknown) {
        const isExpired =
          (err as { statusCode?: number })?.statusCode === 401 ||
          (err as { status?: number })?.status === 401;

        if (isExpired) {
          const freshSession = await recoverExpiredGuestSession();
          setSessionId(freshSession);
          try {
            const fetchedList = await plannerClient.getShoppingList(planIdToFetch, freshSession);
            setShoppingList(fetchedList);
            return;
          } catch {
            // fall through
          }
        }
        setShoppingError(
          err instanceof Error ? err.message : 'Failed to retrieve grocery shopping list.'
        );
      } finally {
        setIsLoadingShopping(false);
      }
    },
    [sessionId]
  );

  // Trigger data fetches when activePlanId or sessionId is ready
  useEffect(() => {
    if (activePlanId && sessionId) {
      fetchMealPlan(activePlanId, sessionId);
      fetchShoppingList(activePlanId, sessionId);
    }
  }, [activePlanId, sessionId, fetchMealPlan, fetchShoppingList]);

  // Save new plan from generator
  const handleSavePlan = async (saveRequest: SaveMealPlanRequest) => {
    setIsMutating(true);
    setPlanError(null);

    const activeSession = sessionId || (await getOrCreateGuestSession());
    setSessionId(activeSession);

    try {
      const summary = await plannerClient.saveMealPlan(saveRequest, activeSession);
      localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, summary.plan_id);
      setActivePlanId(summary.plan_id);
      setShowGenerator(false);
      setActiveTab('schedule');
      await fetchMealPlan(summary.plan_id, activeSession);
      await fetchShoppingList(summary.plan_id, activeSession);
    } catch (err: unknown) {
      const isExpired =
        (err as { statusCode?: number })?.statusCode === 401 ||
        (err as { status?: number })?.status === 401;

      if (isExpired) {
        const freshSession = await recoverExpiredGuestSession();
        setSessionId(freshSession);
        const summary = await plannerClient.saveMealPlan(saveRequest, freshSession);
        localStorage.setItem(ACTIVE_PLAN_STORAGE_KEY, summary.plan_id);
        setActivePlanId(summary.plan_id);
        setShowGenerator(false);
        setActiveTab('schedule');
        await fetchMealPlan(summary.plan_id, freshSession);
        await fetchShoppingList(summary.plan_id, freshSession);
        return;
      }

      setPlanError(
        err instanceof Error ? err.message : 'Failed to save meal plan to guest session.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  // Update cooking status for a slot
  const handleUpdateCookingStatus = async (slotId: number, status: CookingStatus) => {
    if (!plan) return;
    setIsMutating(true);
    setPlanError(null);

    const activeSession = sessionId || (await getOrCreateGuestSession());
    setSessionId(activeSession);

    try {
      await plannerClient.updateCookingProgress(
        plan.id,
        [{ slot_id: slotId, cooking_status: status }],
        activeSession
      );
      // Update local state
      setPlan({
        ...plan,
        slots: plan.slots.map((s) => (s.id === slotId ? { ...s, cooking_status: status } : s)),
      });
    } catch (err: unknown) {
      setPlanError(
        err instanceof Error ? err.message : 'Failed to update cooking progress.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  // Remove a slot from the plan
  const handleRemoveSlot = async (slotId: number) => {
    if (!plan) return;
    setIsMutating(true);
    setPlanError(null);

    const activeSession = sessionId || (await getOrCreateGuestSession());
    setSessionId(activeSession);

    const remainingSlots = plan.slots.filter((s) => s.id !== slotId);
    const updateRequest: SaveMealPlanRequest = {
      name: plan.name,
      days: plan.days,
      target_calories_kcal: plan.target_calories_kcal,
      slots: remainingSlots.map((s) => ({
        day_index: s.day_index,
        slot_type: s.slot_type,
        recipe_id: s.recipe_id,
        recipe_title: s.recipe_title,
      })),
    };

    try {
      const updatedPlan = await plannerClient.updateMealPlan(plan.id, updateRequest, activeSession);
      setPlan(updatedPlan);
      // Invalidate & refresh shopping list as slots changed
      await fetchShoppingList(plan.id, activeSession);
    } catch (err: unknown) {
      setPlanError(
        err instanceof Error ? err.message : 'Failed to update meal plan schedule.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  // Delete current plan
  const handleDeletePlan = async () => {
    if (!plan) return;
    setIsMutating(true);
    setPlanError(null);

    const activeSession = sessionId || (await getOrCreateGuestSession());
    setSessionId(activeSession);

    try {
      await plannerClient.deleteMealPlan(plan.id, activeSession);
      localStorage.removeItem(ACTIVE_PLAN_STORAGE_KEY);
      setActivePlanId(null);
      setPlan(null);
      setShoppingList(null);
      setShowGenerator(false);
    } catch (err: unknown) {
      setPlanError(
        err instanceof Error ? err.message : 'Failed to delete meal plan.'
      );
    } finally {
      setIsMutating(false);
    }
  };

  // Toggle shopping item checkbox
  const handleToggleShoppingItem = async (itemId: number, checked: boolean) => {
    if (!plan || !shoppingList) return;

    const activeSession = sessionId || (await getOrCreateGuestSession());
    setSessionId(activeSession);

    try {
      const updatedItem = await plannerClient.updateShoppingListItem(
        plan.id,
        itemId,
        checked,
        activeSession
      );

      // Update in categories
      const newCategories = shoppingList.categories.map((cat) => ({
        ...cat,
        items: cat.items.map((it) => (it.id === itemId ? { ...it, checked: updatedItem.checked } : it)),
      }));

      setShoppingList({
        ...shoppingList,
        categories: newCategories,
      });
    } catch (err: unknown) {
      setShoppingError(
        err instanceof Error ? err.message : 'Failed to update shopping list item.'
      );
    }
  };

  return (
    <div className="container page-container meal-planner-page" data-testid="meal-planner-page">
      {/* 1. Header */}
      <header className="page-header">
        <span className="editorial-badge">Recommendation &amp; Planner Service :8003</span>
        <h1 className="page-title" data-testid="meal-planner-title">
          Weekly Meal Planning &amp; Macro Optimization
        </h1>
        <p className="page-lead">
          Automated multi-day meal scheduling balanced around energy targets, dietary preferences, and
          consolidated grocery requirements.
        </p>
      </header>

      {/* Global Error Banner */}
      {planError && (
        <div className="status-box error-box" role="alert" data-testid="planner-error-banner">
          <span className="editorial-badge error-badge">Planner Service Error</span>
          <p className="error-text">{planError}</p>
          {activePlanId && (
            <button
              type="button"
              className="btn btn-secondary btn-retry"
              onClick={() => fetchMealPlan(activePlanId)}
              data-testid="retry-plan-btn"
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* 2. Main Viewport */}
      {isLoadingPlan ? (
        <div className="editorial-card loading-card" data-testid="planner-loading-card">
          <span className="editorial-badge">Querying Planner Service</span>
          <p className="loading-text">Loading saved meal plan schedule from guest session...</p>
        </div>
      ) : showGenerator ? (
        <MealPlanGenerator
          onSavePlan={handleSavePlan}
          isSaving={isMutating}
          onCancel={plan ? () => setShowGenerator(false) : undefined}
        />
      ) : plan ? (
        <div className="active-plan-workspace" data-testid="active-plan-workspace">
          {/* Workspace Tabs */}
          <nav aria-label="Planner Views" className="planner-tabs-bar">
            <button
              type="button"
              className={`planner-tab-btn ${activeTab === 'schedule' ? 'active-tab' : ''}`}
              onClick={() => setActiveTab('schedule')}
              data-testid="tab-schedule"
            >
              Weekly Schedule
            </button>
            <button
              type="button"
              className={`planner-tab-btn ${activeTab === 'shopping' ? 'active-tab' : ''}`}
              onClick={() => setActiveTab('shopping')}
              data-testid="tab-shopping-list"
            >
              Shopping List ({shoppingList ? shoppingList.total_items : '...'})
            </button>
            <button
              type="button"
              className={`planner-tab-btn ${activeTab === 'nutrition' ? 'active-tab' : ''}`}
              onClick={() => setActiveTab('nutrition')}
              data-testid="tab-nutrition"
            >
              Nutrition &amp; Plan Info
            </button>
          </nav>

          {/* Tab Content */}
          {activeTab === 'schedule' && (
            <WeeklyOverviewGrid
              plan={plan}
              onUpdateCookingStatus={handleUpdateCookingStatus}
              onRemoveSlot={handleRemoveSlot}
              onDeletePlan={handleDeletePlan}
              onStartNewPlan={() => setShowGenerator(true)}
              isMutating={isMutating}
            />
          )}

          {activeTab === 'shopping' && (
            <ShoppingListSection
              shoppingList={shoppingList}
              isLoading={isLoadingShopping}
              error={shoppingError}
              onRetry={() => plan && fetchShoppingList(plan.id)}
              onToggleItem={handleToggleShoppingItem}
              isMutating={isMutating}
            />
          )}

          {activeTab === 'nutrition' && <MealPlanNutritionSummary plan={plan} />}
        </div>
      ) : (
        /* Empty State: Informative onboarding with clear CTA */
        <div className="editorial-card empty-planner-card" data-testid="empty-planner-state">
          <span className="editorial-badge">Guest Session Ready</span>
          <h2 className="empty-title" data-testid="empty-planner-title">
            No Active Meal Plan
          </h2>
          <p className="empty-desc">
            You do not currently have a saved meal plan. NutriPod can automatically synthesize a
            balanced 1 to 14-day schedule matching your dietary preferences, daily caloric boundary,
            and preparation time limits.
          </p>

          <div className="empty-actions">
            <button
              type="button"
              className="btn btn-primary btn-generate-cta"
              onClick={() => setShowGenerator(true)}
              data-testid="create-plan-cta-btn"
            >
              Generate Weekly Meal Plan &rarr;
            </button>
          </div>

          <div className="how-it-works-grid">
            <div className="feature-card">
              <span className="feature-number">01</span>
              <h3 className="feature-title">Multi-Slot Scheduling</h3>
              <p className="feature-desc">
                Configure Breakfast, Lunch, Dinner, and Snack allocations across your preferred day horizon.
              </p>
            </div>
            <div className="feature-card">
              <span className="feature-number">02</span>
              <h3 className="feature-title">Diversity &amp; Caloric Balancing</h3>
              <p className="feature-desc">
                Our recommendation engine queries 50,000 catalogued recipes, avoiding excessive repetition.
              </p>
            </div>
            <div className="feature-card">
              <span className="feature-number">03</span>
              <h3 className="feature-title">Automatic Grocery Checklist</h3>
              <p className="feature-desc">
                Ingredients are automatically aggregated and organized by supermarket aisle for effortless shopping.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* 3. Architectural Overview Footer */}
      <div className="page-grid spec-grid">
        <div className="editorial-card info-card">
          <h2 className="card-heading">Planner Architecture</h2>
          <ul className="spec-list">
            <li>
              <strong>Dynamic Day Horizon:</strong> Configurable 1 to 14 day planning horizon.
            </li>
            <li>
              <strong>Meal Slots:</strong> Structured daily allocations for breakfast, lunch, dinner,
              and snacks.
            </li>
            <li>
              <strong>Caloric Target:</strong> Optional daily boundary without requiring mandatory
              biometrics.
            </li>
            <li>
              <strong>Diversity Safeguard:</strong> Balances recipe variety across adjacent days.
            </li>
            <li>
              <strong>Cooking Execution:</strong> Interactive slot tracking across <code>pending</code>,{' '}
              <code>cooked</code>, and <code>skipped</code> states.
            </li>
          </ul>
        </div>

        <div className="editorial-card info-card">
          <h2 className="card-heading">AMDR Macronutrient Grounding</h2>
          <p className="card-body-text">
            Macronutrient targets conform to authoritative dietary reference standards:
          </p>
          <ul className="spec-list">
            <li>
              <strong>Protein Target:</strong> 20% of total daily energy (range 10–35%).
            </li>
            <li>
              <strong>Carbohydrates Target:</strong> 50% of total daily energy (range 45–65%).
            </li>
            <li>
              <strong>Fat Target:</strong> 30% of total daily energy (range 20–35%).
            </li>
            <li>
              <strong>Total Distribution:</strong> Strictly calibrated to 100% of daily intake.
            </li>
          </ul>
        </div>
      </div>

      <style>{`
        .meal-planner-page {
          padding-top: var(--space-8);
          padding-bottom: var(--space-12);
          display: flex;
          flex-direction: column;
          gap: var(--space-8);
        }

        .page-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-6);
        }

        .page-title {
          font-family: var(--font-serif);
          font-size: var(--text-3xl);
          font-weight: 700;
          margin: 0;
        }

        .page-lead {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
          max-width: 800px;
          margin: 0;
        }

        .planner-tabs-bar {
          display: flex;
          gap: var(--space-2);
          border-bottom: 2px solid var(--color-border);
          padding-bottom: 0px;
        }

        .planner-tab-btn {
          padding: 0.6rem 1.2rem;
          font-size: var(--text-sm);
          font-weight: 600;
          background: transparent;
          border: 1px solid var(--color-border);
          border-bottom: none;
          border-radius: 0px !important;
          cursor: pointer;
          color: var(--color-text-secondary);
          margin-bottom: -2px;
        }

        .planner-tab-btn.active-tab {
          background: var(--color-surface);
          color: var(--color-text);
          border-color: var(--color-text);
          border-bottom: 2px solid var(--color-surface);
        }

        .active-plan-workspace {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }

        .empty-planner-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          padding: var(--space-8);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          background: var(--color-surface);
        }

        .empty-title {
          font-family: var(--font-serif);
          font-size: var(--text-3xl);
          font-weight: 700;
          margin: 0;
        }

        .empty-desc {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
          max-width: 700px;
          margin: 0;
          line-height: 1.5;
        }

        .empty-actions {
          margin-top: var(--space-2);
        }

        .btn-generate-cta {
          padding: 0.8rem 1.6rem;
          font-size: var(--text-base);
          font-weight: 600;
        }

        .how-it-works-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: var(--space-5);
          margin-top: var(--space-6);
          border-top: 1px solid var(--color-border);
          padding-top: var(--space-6);
        }

        .feature-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .feature-number {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          color: var(--color-accent, #c2410c);
        }

        .feature-title {
          font-family: var(--font-serif);
          font-size: var(--text-base);
          font-weight: 700;
          margin: 0;
        }

        .feature-desc {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
          margin: 0;
          line-height: 1.4;
        }

        .status-box {
          padding: var(--space-4);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .error-box {
          border-color: #b91c1c;
          background-color: rgba(185, 28, 28, 0.05);
        }

        .error-text {
          color: #b91c1c;
          margin: 0;
          font-size: var(--text-sm);
        }

        .loading-card {
          padding: var(--space-8);
          text-align: center;
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          align-items: center;
        }

        .loading-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .page-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: var(--space-6);
        }

        .info-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          padding: var(--space-6);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          background: var(--color-surface);
        }

        .card-heading {
          font-size: var(--text-xl);
          font-family: var(--font-serif);
          margin: 0;
        }

        .card-body-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          margin: 0;
        }

        .spec-list {
          list-style: square;
          margin: 0 0 0 var(--space-5);
          padding: 0;
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .spec-list strong {
          color: var(--color-text);
        }
      `}</style>
    </div>
  );
};
