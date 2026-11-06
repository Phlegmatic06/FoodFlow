import React, { useState, useCallback, useRef } from 'react';
import { recipeClient } from '../../api/recipeClient';
import { profileClient } from '../../api/profileClient';
import { RecipeDetail } from '../../api/types/recipe';
import { RecipeNutritionEstimateResponse } from '../../api/types/profile';

export const RecipeNutritionEstimator: React.FC = () => {
  const [recipeIdInput, setRecipeIdInput] = useState<string>('');
  const [activeRecipeId, setActiveRecipeId] = useState<string>('');
  const [recipe, setRecipe] = useState<RecipeDetail | null>(null);
  const [estimateResult, setEstimateResult] = useState<RecipeNutritionEstimateResponse | null>(null);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  const handleEstimate = useCallback(async (targetId: string) => {
    const cleanId = targetId.trim();
    if (!cleanId) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setErrorMessage(null);
    setRecipe(null);
    setEstimateResult(null);
    setActiveRecipeId(cleanId);

    try {
      // 1. Fetch recipe details from Recipe Service (:8002)
      const recipeData = await recipeClient.getRecipe(cleanId, {
        signal: controller.signal,
      });
      setRecipe(recipeData);

      // Check if ingredients exist
      if (!recipeData.ingredients || recipeData.ingredients.length === 0) {
        setErrorMessage(`Recipe '${cleanId}' contains no ingredients to estimate.`);
        return;
      }

      // 2. Trigger on-demand estimation via Profile Service (:8001)
      const estimate = await profileClient.estimateRecipeNutrition(
        {
          servings: recipeData.servings && recipeData.servings > 0 ? recipeData.servings : 1,
          ingredients: recipeData.ingredients.map((ing) => ({
            raw_text: ing.raw_text,
            canonical_name: ing.canonical_name,
            quantity: ing.quantity,
            unit: ing.unit,
          })),
        },
        { signal: controller.signal }
      );
      setEstimateResult(estimate);
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setErrorMessage(
        err instanceof Error
          ? err.message
          : `Failed to estimate nutritional profile for recipe '${cleanId}'.`
      );
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleEstimate(recipeIdInput);
  };

  const formatMetric = (val: number | null | undefined, unit: string) => {
    if (val === null || val === undefined) return <span className="val-na">Unavailable</span>;
    return (
      <span className="val-num">
        {Number.isInteger(val) ? val.toString() : val.toFixed(1)} <span className="val-u">{unit}</span>
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'calculated':
        return <span className="editorial-badge status-calculated" data-testid="estimator-status-badge">USDA Estimated (Calculated)</span>;
      case 'partial':
        return <span className="editorial-badge status-partial" data-testid="estimator-status-badge">Partial Coverage (&lt; 80%)</span>;
      case 'uncalculated':
        return <span className="editorial-badge status-uncalculated" data-testid="estimator-status-badge">Uncalculated</span>;
      default:
        return <span className="editorial-badge" data-testid="estimator-status-badge">{status}</span>;
    }
  };

  return (
    <section className="recipe-estimator-section" data-testid="recipe-estimator-section">
      <div className="section-header-block">
        <span className="editorial-badge">Algorithmic Decomposition</span>
        <h2 className="section-title" data-testid="estimator-heading">
          Recipe Nutrition Estimator
        </h2>
        <p className="section-lead">
          Execute real-time USDA nutritional decomposition against any catalogue recipe. The Profile
          &amp; Nutrition Service (:8001) parses ingredient phrases, resolves FDC laboratory items,
          and calculates aggregate macro totals without browser-side heuristics.
        </p>
      </div>

      <div className="estimator-layout-grid">
        {/* Input Panel */}
        <div className="estimator-input-column">
          <form
            className="editorial-card estimator-form"
            onSubmit={handleSubmit}
            data-testid="estimator-form"
          >
            <div className="form-group">
              <label htmlFor="recipe-id-input" className="form-label">
                Recipe Identifier (Global ID)
              </label>
              <div className="input-with-button">
                <input
                  id="recipe-id-input"
                  type="text"
                  className="form-input"
                  placeholder="e.g. rcp_foodcom_358911 or rcp_nlg_1914325"
                  value={recipeIdInput}
                  onChange={(e) => setRecipeIdInput(e.target.value)}
                  required
                  data-testid="estimator-id-input"
                />
                <button
                  type="submit"
                  className="btn btn-primary btn-estimate"
                  disabled={isLoading}
                  data-testid="estimator-submit-btn"
                >
                  {isLoading ? 'Estimating...' : 'Analyze Recipe →'}
                </button>
              </div>
            </div>

            <div className="quick-recipe-chips">
              <span className="chips-label">Quick Samples:</span>
              <button
                type="button"
                className="chip-btn"
                onClick={() => {
                  setRecipeIdInput('rcp_foodcom_358911');
                  handleEstimate('rcp_foodcom_358911');
                }}
                data-testid="sample-chip-foodcom"
              >
                Food.com (#358911)
              </button>
              <button
                type="button"
                className="chip-btn"
                onClick={() => {
                  setRecipeIdInput('rcp_nlg_1914325');
                  handleEstimate('rcp_nlg_1914325');
                }}
                data-testid="sample-chip-nlg"
              >
                RecipeNLG (#1914325)
              </button>
            </div>
          </form>

          {/* Recipe Context Summary if loaded */}
          {recipe && (
            <div className="editorial-card recipe-context-card" data-testid="recipe-context-card">
              <div className="context-header">
                <span className="editorial-badge">Target Recipe</span>
                <span className="recipe-ds-badge">{recipe.source_dataset}</span>
              </div>
              <h3 className="recipe-context-title" data-testid="estimator-recipe-title">
                {recipe.title}
              </h3>
              <p className="recipe-context-meta">
                {recipe.ingredients.length} ingredients &bull; Yield:{' '}
                {recipe.servings ? `${recipe.servings} servings` : '1 serving (default yield)'}
              </p>
            </div>
          )}
        </div>

        {/* Results Panel */}
        <div className="estimator-results-column" data-testid="estimator-results-column">
          {isLoading ? (
            <div className="editorial-card status-card" data-testid="estimator-loading">
              <p>Analyzing recipe ingredients and aggregating USDA nutrient profiles...</p>
            </div>
          ) : errorMessage ? (
            <div className="editorial-card error-card" data-testid="estimator-error">
              <span className="editorial-badge error-badge">Estimation Error</span>
              <p className="error-text">{errorMessage}</p>
              <button
                type="button"
                className="btn btn-secondary btn-retry"
                onClick={() => handleEstimate(activeRecipeId)}
                data-testid="estimator-retry-btn"
              >
                Retry Analysis
              </button>
            </div>
          ) : !estimateResult ? (
            <div className="editorial-card placeholder-card" data-testid="estimator-placeholder">
              <span className="editorial-badge">Awaiting Recipe</span>
              <h3 className="placeholder-title">No Recipe Analyzed</h3>
              <p className="placeholder-text">
                Enter a recipe ID or click one of the quick samples to run algorithmic USDA
                nutrition decomposition across all ingredient items.
              </p>
            </div>
          ) : (
            <div className="editorial-card estimate-active-card" data-testid="estimator-result-card">
              <div className="estimate-top-strip">
                <div>
                  <span className="eval-tag">Profile Service USDA Decomposition</span>
                  <div className="status-badge-wrapper">{getStatusBadge(estimateResult.status)}</div>
                </div>
                <div className="coverage-pill" data-testid="estimator-coverage">
                  <span className="coverage-label">Coverage:</span>
                  <span className="coverage-pct">{estimateResult.ingredient_coverage.coverage_pct.toFixed(0)}%</span>
                  <span className="coverage-counts">
                    ({estimateResult.ingredient_coverage.mapped_count} of{' '}
                    {estimateResult.ingredient_coverage.total_count} mapped)
                  </span>
                </div>
              </div>

              {/* Status explanation for partial / uncalculated */}
              {estimateResult.status === 'uncalculated' && (
                <div className="uncalculated-alert" data-testid="estimator-uncalculated-alert">
                  <p>
                    Ingredient coverage was insufficient to calculate a reliable USDA nutritional estimate.
                  </p>
                </div>
              )}

              {/* Unmapped Ingredients list */}
              {estimateResult.unmapped_ingredients && estimateResult.unmapped_ingredients.length > 0 && (
                <div className="unmapped-container" data-testid="unmapped-ingredients-list">
                  <span className="unmapped-title">Unmapped Ingredients ({estimateResult.unmapped_ingredients.length}):</span>
                  <ul className="unmapped-list">
                    {estimateResult.unmapped_ingredients.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Per-Serving Metrics Grid */}
              {estimateResult.per_serving && (
                <div className="metrics-section">
                  <h4 className="metrics-heading">
                    Per-Serving Nutrient Profile (Yield: {estimateResult.servings})
                  </h4>
                  <div className="metrics-grid" data-testid="estimator-metrics-grid">
                    <div className="nutrient-cell highlight-cell" data-testid="est-calories">
                      <span className="cell-label">Calories</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.calories_kcal, 'kcal')}
                      </span>
                    </div>

                    <div className="nutrient-cell" data-testid="est-protein">
                      <span className="cell-label">Protein</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.protein_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-cell" data-testid="est-carbs">
                      <span className="cell-label">Carbohydrates</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.carbohydrates_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-cell" data-testid="est-fat">
                      <span className="cell-label">Total Fat</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.total_fat_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-cell" data-testid="est-sat-fat">
                      <span className="cell-label">Saturated Fat</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.saturated_fat_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-cell" data-testid="est-fiber">
                      <span className="cell-label">Dietary Fiber</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.fiber_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-cell" data-testid="est-sugar">
                      <span className="cell-label">Sugars</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.sugar_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-cell" data-testid="est-sodium">
                      <span className="cell-label">Sodium</span>
                      <span className="cell-val">
                        {formatMetric(estimateResult.per_serving.sodium_mg, 'mg')}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Provenance note & disclaimer */}
              {estimateResult.provenance_note && (
                <p className="provenance-note" data-testid="est-provenance-note">
                  {estimateResult.provenance_note}
                </p>
              )}

              <p className="disclaimer-text" data-testid="est-disclaimer">
                {estimateResult.disclaimer}
              </p>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .recipe-estimator-section {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }

        .section-header-block {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-4);
        }

        .section-title {
          font-size: var(--text-2xl);
          font-weight: 700;
        }

        .section-lead {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          max-width: 800px;
          line-height: 1.6;
        }

        .estimator-layout-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-6);
        }

        @media (min-width: 900px) {
          .estimator-layout-grid {
            grid-template-columns: 1fr 1.2fr;
          }
        }

        .estimator-input-column {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .estimator-form {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          background-color: var(--color-surface);
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .form-label {
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
        }

        .input-with-button {
          display: flex;
          gap: var(--space-2);
        }

        .input-with-button .form-input {
          flex: 1;
        }

        .btn-estimate {
          white-space: nowrap;
          font-size: var(--text-xs);
        }

        .quick-recipe-chips {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          flex-wrap: wrap;
        }

        .chips-label {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-weight: 700;
          text-transform: uppercase;
        }

        .chip-btn {
          font-size: 0.72rem;
          color: var(--color-accent);
          background-color: var(--color-accent-subtle);
          padding: 0.15rem 0.4rem;
          border: 1px solid var(--color-accent);
          cursor: pointer;
        }

        .chip-btn:hover {
          background-color: var(--color-accent);
          color: #ffffff;
        }

        .recipe-context-card {
          padding: var(--space-4);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .context-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .recipe-ds-badge {
          font-size: 0.7rem;
          text-transform: uppercase;
          color: var(--color-text-muted);
        }

        .recipe-context-title {
          font-family: var(--font-serif);
          font-size: var(--text-base);
          font-weight: 700;
        }

        .recipe-context-meta {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
        }

        /* Results Column */
        .status-card, .error-card, .placeholder-card, .estimate-active-card {
          height: 100%;
          padding: var(--space-6);
          background-color: var(--color-surface);
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .placeholder-title {
          font-size: var(--text-base);
          font-family: var(--font-serif);
        }

        .placeholder-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .estimate-top-strip {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          flex-wrap: wrap;
          gap: var(--space-3);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-3);
        }

        .eval-tag {
          font-size: 0.72rem;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--color-text-muted);
          display: block;
          margin-bottom: var(--space-1);
        }

        .coverage-pill {
          display: flex;
          align-items: center;
          gap: var(--space-1);
          font-size: var(--text-xs);
          background-color: var(--color-surface-subtle);
          padding: var(--space-1) var(--space-2);
          border: 1px solid var(--color-border);
        }

        .coverage-pct {
          font-weight: 700;
          color: var(--color-accent);
        }

        .coverage-counts {
          color: var(--color-text-muted);
        }

        .status-calculated {
          background-color: var(--color-success-subtle);
          color: var(--color-success);
          border-color: var(--color-success);
        }

        .status-partial {
          background-color: var(--color-accent-subtle);
          color: var(--color-accent);
          border-color: var(--color-accent);
        }

        .status-uncalculated {
          background-color: var(--color-surface-subtle);
          color: var(--color-text-muted);
        }

        .uncalculated-alert {
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-style: italic;
        }

        .unmapped-container {
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border-left: 2px solid var(--color-accent);
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .unmapped-title {
          font-size: var(--text-xs);
          font-weight: 700;
          color: var(--color-text-secondary);
          text-transform: uppercase;
        }

        .unmapped-list {
          padding-left: var(--space-4);
          font-size: var(--text-xs);
          color: var(--color-text-muted);
        }

        .metrics-section {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .metrics-heading {
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          color: var(--color-text-muted);
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--space-2);
        }

        @media (min-width: 600px) {
          .metrics-grid {
            grid-template-columns: repeat(4, 1fr);
          }
        }

        .nutrient-cell {
          padding: var(--space-2) var(--space-3);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .highlight-cell {
          border-color: var(--color-accent);
          background-color: var(--color-accent-subtle);
        }

        .cell-label {
          font-size: 0.68rem;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--color-text-muted);
        }

        .cell-val {
          font-size: var(--text-base);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .val-num {
          color: var(--color-text-primary);
        }

        .val-u {
          font-size: 0.75rem;
          font-weight: 400;
          color: var(--color-text-muted);
        }

        .val-na {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-style: italic;
        }

        .provenance-note {
          font-size: 0.72rem;
          color: var(--color-text-secondary);
          border-left: 2px solid var(--color-border-strong);
          padding-left: var(--space-2);
          line-height: 1.4;
        }

        .disclaimer-text {
          font-size: 0.7rem;
          color: var(--color-text-muted);
          line-height: 1.4;
        }
      `}</style>
    </section>
  );
};

