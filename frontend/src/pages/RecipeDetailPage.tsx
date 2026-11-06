import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { recipeClient } from '../api/recipeClient';
import { profileClient } from '../api/profileClient';
import { RecipeDetail } from '../api/types/recipe';
import { CachedRecipeNutrition } from '../api/types/profile';
import { ApiError } from '../api/types/common';
import { RecipeDetailHeader } from '../components/recipes/RecipeDetailHeader';
import { RecipeIngredients } from '../components/recipes/RecipeIngredients';
import { RecipeInstructions } from '../components/recipes/RecipeInstructions';
import { RecipeNutritionPanel } from '../components/recipes/RecipeNutritionPanel';
import { CookingMode } from '../components/recipes/CookingMode';

const STORAGE_PREFIX = 'foodflow_cooking_';

interface PersistedCookingState {
  currentStep: number;
  checkedPositions: number[];
  updatedAt?: string;
}

function loadPersistedCookingState(
  recipeId: string,
  totalSteps: number
): { currentStep: number; checked: Set<number> } {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${recipeId}`);
    if (!raw) return { currentStep: 0, checked: new Set<number>() };

    const parsed = JSON.parse(raw) as Partial<PersistedCookingState>;
    let step = 0;
    if (
      typeof parsed?.currentStep === 'number' &&
      Number.isInteger(parsed.currentStep) &&
      parsed.currentStep >= 0
    ) {
      step = totalSteps > 0 ? Math.min(parsed.currentStep, totalSteps - 1) : 0;
    }

    const checked = new Set<number>();
    if (Array.isArray(parsed?.checkedPositions)) {
      for (const pos of parsed.checkedPositions) {
        if (typeof pos === 'number' && Number.isInteger(pos)) {
          checked.add(pos);
        }
      }
    }

    return { currentStep: step, checked };
  } catch {
    return { currentStep: 0, checked: new Set<number>() };
  }
}

function savePersistedCookingState(
  recipeId: string,
  currentStep: number,
  checked: Set<number>
) {
  try {
    const payload: PersistedCookingState = {
      currentStep,
      checkedPositions: Array.from(checked),
      updatedAt: new Date().toISOString(),
    };
    localStorage.setItem(`${STORAGE_PREFIX}${recipeId}`, JSON.stringify(payload));
  } catch {
    // Safely swallow storage exceptions (quota exceeded, private browsing, etc.)
  }
}

export const RecipeDetailPage: React.FC = () => {
  const { recipeId } = useParams<{ recipeId: string }>();

  const [recipe, setRecipe] = useState<RecipeDetail | null>(null);
  const [isLoadingRecipe, setIsLoadingRecipe] = useState<boolean>(true);
  const [recipeError, setRecipeError] = useState<string | null>(null);
  const [is404, setIs404] = useState<boolean>(false);

  // Nutrition state from Profile Service (:8001)
  const [cachedNutrition, setCachedNutrition] = useState<CachedRecipeNutrition | null>(null);
  const [isLoadingNutrition, setIsLoadingNutrition] = useState<boolean>(false);
  const [nutritionError, setNutritionError] = useState<string | null>(null);
  const [isEstimatingNutrition, setIsEstimatingNutrition] = useState<boolean>(false);
  const [nutritionEstimateError, setNutritionEstimateError] = useState<string | null>(null);

  // Interactive Cooking Mode & Checklist State
  const [isCookingMode, setIsCookingMode] = useState<boolean>(false);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [checkedIngredients, setCheckedIngredients] = useState<Set<number>>(new Set());

  // Ref to track active request abort controller
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchRecipeData = useCallback(async (id: string) => {
    // Abort previous in-flight request if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoadingRecipe(true);
    setRecipeError(null);
    setIs404(false);
    setRecipe(null);
    setCachedNutrition(null);
    setNutritionError(null);

    try {
      // 1. Fetch recipe details from Recipe Service (:8002)
      const data = await recipeClient.getRecipe(id, { signal: controller.signal });
      setRecipe(data);

      // Hydrate persisted cooking progress & checklist for this specific recipe
      const persisted = loadPersistedCookingState(id, data.instructions?.length || 0);
      setCurrentStepIndex(persisted.currentStep);
      setCheckedIngredients(persisted.checked);

      // 2. Fetch USDA estimated nutrition from Profile Service (:8001)
      setIsLoadingNutrition(true);
      try {
        const nutritionData = await profileClient.getRecipeNutrition(id, {
          signal: controller.signal,
        });
        setCachedNutrition(nutritionData);
      } catch (nutrErr: unknown) {
        if (controller.signal.aborted) return;
        // 404 is an expected state for recipes without a precomputed USDA estimate
        const isNutr404 =
          (nutrErr instanceof ApiError && nutrErr.statusCode === 404) ||
          (nutrErr as { statusCode?: number })?.statusCode === 404 ||
          (nutrErr as { status?: number })?.status === 404;

        if (!isNutr404) {
          setNutritionError(
            nutrErr instanceof Error ? nutrErr.message : 'Failed to query nutritional profile'
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoadingNutrition(false);
        }
      }
    } catch (err: unknown) {
      if (controller.signal.aborted) return;

      const isNotFound =
        (err instanceof ApiError && err.statusCode === 404) ||
        (err as { statusCode?: number })?.statusCode === 404 ||
        (err as { status?: number })?.status === 404 ||
        (err instanceof Error && /404|not found/i.test(err.message));

      if (isNotFound) {
        setIs404(true);
        setRecipeError(`Recipe '${id}' was not found in the catalogue.`);
      } else {
        setRecipeError(
          err instanceof Error ? err.message : 'An error occurred while loading recipe details.'
        );
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsLoadingRecipe(false);
      }
    }
  }, []);

  useEffect(() => {
    if (recipeId) {
      fetchRecipeData(recipeId);
    } else {
      setIs404(true);
      setIsLoadingRecipe(false);
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [recipeId, fetchRecipeData]);

  // Handle ingredient checklist toggles
  const handleToggleIngredient = useCallback(
    (position: number) => {
      if (!recipeId) return;
      setCheckedIngredients((prev) => {
        const next = new Set(prev);
        if (next.has(position)) {
          next.delete(position);
        } else {
          next.add(position);
        }
        savePersistedCookingState(recipeId, currentStepIndex, next);
        return next;
      });
    },
    [recipeId, currentStepIndex]
  );

  const handleResetChecklist = useCallback(() => {
    if (!recipeId) return;
    const emptySet = new Set<number>();
    setCheckedIngredients(emptySet);
    savePersistedCookingState(recipeId, currentStepIndex, emptySet);
  }, [recipeId, currentStepIndex]);

  // Handle cooking mode step changes
  const handleStepChange = useCallback(
    (newIndex: number) => {
      if (!recipeId) return;
      setCurrentStepIndex(newIndex);
      savePersistedCookingState(recipeId, newIndex, checkedIngredients);
    },
    [recipeId, checkedIngredients]
  );

  const handleEnterCookingMode = useCallback(() => {
    setIsCookingMode(true);
  }, []);

  const handleExitCookingMode = useCallback(() => {
    setIsCookingMode(false);
  }, []);

  // Trigger on-demand USDA nutrition estimate for recipes without cached profile
  const handleCalculateNutrition = useCallback(async () => {
    if (!recipe) return;
    setIsEstimatingNutrition(true);
    setNutritionEstimateError(null);

    try {
      const ingredientInputs = (recipe.ingredients || []).map((ing) => ({
        raw_text: ing.raw_text,
        canonical_name: ing.canonical_name ?? null,
        quantity: ing.quantity ?? null,
        unit: ing.unit ?? null,
      }));

      const result = await profileClient.estimateRecipeNutrition({
        servings: recipe.servings || 1,
        ingredients: ingredientInputs,
      });

      const adapted: CachedRecipeNutrition = {
        recipe_id: recipe.id,
        status: result.status,
        ingredient_coverage_pct: result.ingredient_coverage?.coverage_pct ?? null,
        mapped_ingredient_count: result.ingredient_coverage?.mapped_count ?? null,
        total_ingredient_count: result.ingredient_coverage?.total_count ?? null,
        servings: result.servings ?? recipe.servings ?? 1,
        calories_kcal: result.per_serving?.calories_kcal ?? null,
        protein_g: result.per_serving?.protein_g ?? null,
        total_fat_g: result.per_serving?.total_fat_g ?? null,
        saturated_fat_g: result.per_serving?.saturated_fat_g ?? null,
        carbohydrates_g: result.per_serving?.carbohydrates_g ?? null,
        fiber_g: result.per_serving?.fiber_g ?? null,
        sodium_mg: result.per_serving?.sodium_mg ?? null,
        calculated_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      setCachedNutrition(adapted);
    } catch (err: unknown) {
      setNutritionEstimateError(
        err instanceof Error ? err.message : 'Failed to calculate USDA nutrition estimate'
      );
    } finally {
      setIsEstimatingNutrition(false);
    }
  }, [recipe]);

  // Loading View
  if (isLoadingRecipe) {
    return (
      <div className="container page-container" data-testid="recipe-loading">
        <div className="editorial-card loading-card">
          <span className="editorial-badge">Retrieving Record</span>
          <h2 className="loading-title">Loading Recipe Details...</h2>
          <p className="loading-lead">
            Querying Recipe &amp; Ingredient Service (:8002) for verified ingredients and procedural steps.
          </p>
        </div>
      </div>
    );
  }

  // Not Found View (404)
  if (is404) {
    return (
      <div className="container page-container" data-testid="recipe-not-found">
        <nav aria-label="Breadcrumb" className="breadcrumb-nav">
          <ol className="breadcrumb-list">
            <li className="breadcrumb-item">
              <Link to="/" className="breadcrumb-link">Home</Link>
            </li>
            <li className="breadcrumb-separator" aria-hidden="true">&gt;</li>
            <li className="breadcrumb-item">
              <Link to="/recipes" className="breadcrumb-link">Recipes</Link>
            </li>
            <li className="breadcrumb-separator" aria-hidden="true">&gt;</li>
            <li className="breadcrumb-item breadcrumb-current" aria-current="page">
              Not Found
            </li>
          </ol>
        </nav>

        <div className="editorial-card not-found-card">
          <span className="editorial-badge error-badge">404 Not Found</span>
          <h1 className="not-found-title">Recipe Not Found</h1>
          <p className="not-found-text">
            {recipeError || `The requested recipe '${recipeId}' could not be located in the catalogue.`}
          </p>
          <div className="not-found-actions">
            <Link to="/recipes" className="btn btn-primary" data-testid="back-to-recipes-btn">
              &larr; Back to Recipe Discovery
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // General Network / API Error View
  if (recipeError || !recipe) {
    return (
      <div className="container page-container" data-testid="recipe-error">
        <div className="editorial-card error-card">
          <span className="editorial-badge error-badge">Service Error</span>
          <h1 className="error-card-title">Failed to Load Recipe</h1>
          <p className="error-card-text">
            {recipeError || 'An unexpected communication error occurred with the Recipe Service.'}
          </p>
          <div className="error-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => recipeId && fetchRecipeData(recipeId)}
              data-testid="recipe-retry-btn"
            >
              Retry Connection
            </button>
            <Link to="/recipes" className="btn btn-secondary">
              Back to Recipes
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // If in interactive Cooking Mode
  if (isCookingMode && recipe.instructions && recipe.instructions.length > 0) {
    return (
      <CookingMode
        recipeTitle={recipe.title}
        instructions={recipe.instructions}
        ingredients={recipe.ingredients}
        currentStepIndex={currentStepIndex}
        onStepChange={handleStepChange}
        onExit={handleExitCookingMode}
        checkedIngredients={checkedIngredients}
        onToggleIngredient={handleToggleIngredient}
      />
    );
  }

  // Standard Recipe Detail View
  const hasInstructions = Boolean(recipe.instructions && recipe.instructions.length > 0);

  return (
    <div className="container page-container recipe-detail-page" data-testid="recipe-detail-page">
      {/* 1. Header Section */}
      <RecipeDetailHeader
        recipe={recipe}
        onEnterCookingMode={handleEnterCookingMode}
        hasInstructions={hasInstructions}
      />

      {/* 2. Main Content Grid: Ingredients & Instructions */}
      <div className="recipe-content-grid">
        <div className="content-primary-column">
          <RecipeIngredients
            ingredients={recipe.ingredients}
            checkedPositions={checkedIngredients}
            onToggleIngredient={handleToggleIngredient}
            onResetChecklist={handleResetChecklist}
          />

          <RecipeInstructions
            instructions={recipe.instructions}
            onEnterCookingMode={handleEnterCookingMode}
            activeStepNumber={hasInstructions ? currentStepIndex + 1 : undefined}
          />
        </div>

        {/* 3. Nutrition & Provenance Sidebar */}
        <aside className="content-sidebar-column">
          <RecipeNutritionPanel
            rawNutrition={recipe.raw_nutrition}
            cachedNutrition={cachedNutrition}
            isLoadingNutrition={isLoadingNutrition}
            nutritionError={nutritionError}
            sourceDataset={recipe.source_dataset}
            servings={recipe.servings}
            onTriggerEstimate={handleCalculateNutrition}
            isEstimating={isEstimatingNutrition}
            estimateError={nutritionEstimateError}
          />
        </aside>
      </div>

      {/* 4. Footer Discovery Navigation */}
      <div className="page-footer-nav">
        <Link
          to="/recipes"
          className="btn btn-secondary back-to-discovery-btn"
          data-testid="bottom-back-to-recipes"
        >
          &larr; Back to Recipe Discovery
        </Link>
      </div>

      <style>{`
        .page-container {
          padding-top: var(--space-8);
          padding-bottom: var(--space-16);
          display: flex;
          flex-direction: column;
          gap: var(--space-8);
        }

        .loading-card, .not-found-card, .error-card {
          padding: var(--space-8);
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          max-width: 650px;
          margin: var(--space-8) auto;
        }

        .loading-title, .not-found-title, .error-card-title {
          font-size: var(--text-3xl);
          font-weight: 700;
        }

        .loading-lead, .not-found-text, .error-card-text {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
          line-height: 1.6;
        }

        .not-found-actions, .error-actions {
          display: flex;
          gap: var(--space-3);
          margin-top: var(--space-2);
        }

        .error-badge {
          background-color: var(--color-error-subtle);
          color: var(--color-error);
          border-color: var(--color-error);
          align-self: flex-start;
        }

        .recipe-content-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-8);
        }

        @media (min-width: 900px) {
          .recipe-content-grid {
            grid-template-columns: 1.4fr 1fr;
          }
        }

        .content-primary-column {
          display: flex;
          flex-direction: column;
          gap: var(--space-8);
        }

        .content-sidebar-column {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }

        .page-footer-nav {
          padding-top: var(--space-6);
          border-top: 1px solid var(--color-border);
        }

        .back-to-discovery-btn {
          font-size: var(--text-sm);
        }
      `}</style>
    </div>
  );
};
