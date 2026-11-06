import React from 'react';
import { RecipeRawNutrition } from '../../api/types/recipe';
import { CachedRecipeNutrition } from '../../api/types/profile';

interface RecipeNutritionPanelProps {
  rawNutrition?: RecipeRawNutrition | null;
  cachedNutrition?: CachedRecipeNutrition | null;
  isLoadingNutrition: boolean;
  nutritionError?: string | null;
  sourceDataset: 'food_com' | 'recipenlg';
  servings?: number | null;
  onTriggerEstimate?: () => Promise<void> | void;
  isEstimating?: boolean;
  estimateError?: string | null;
}

export const RecipeNutritionPanel: React.FC<RecipeNutritionPanelProps> = ({
  rawNutrition,
  cachedNutrition,
  isLoadingNutrition,
  nutritionError,
  sourceDataset,
  servings,
  onTriggerEstimate,
  isEstimating = false,
  estimateError = null,
}) => {
  // Check if we have any nutrition information
  const hasRawNutrition = rawNutrition !== null && rawNutrition !== undefined;
  const hasCachedNutrition = cachedNutrition !== null && cachedNutrition !== undefined;

  // Format metric value helper: never display missing as zero!
  const formatMetric = (
    val: number | null | undefined,
    unit: string,
    precision = 1
  ): string => {
    if (val === null || val === undefined) return 'Unavailable';
    return `${Number.isInteger(val) ? val.toString() : val.toFixed(precision)} ${unit}`;
  };

  const formatPercentage = (
    val: number | null | undefined
  ): string => {
    if (val === null || val === undefined) return 'Unavailable';
    return `${Number.isInteger(val) ? val.toString() : val.toFixed(1)}% DV`;
  };

  // Status mapping for USDA estimates
  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'calculated':
        return 'USDA Estimated (Calculated)';
      case 'reported_approximate':
        return 'Reported Approximate';
      case 'partial':
        return 'Partial Coverage';
      case 'uncalculated':
        return 'Uncalculated';
      default:
        return status;
    }
  };

  return (
    <section className="recipe-nutrition-panel" data-testid="recipe-nutrition-panel">
      <div className="section-header-row">
        <div>
          <h2 className="section-heading" data-testid="nutrition-heading">
            Nutritional Profile &amp; Analysis
          </h2>
          <span className="nutrition-subtitle">
            Macronutrient decomposition &amp; USDA SR Legacy estimations
          </span>
        </div>
      </div>

      {isLoadingNutrition ? (
        <div className="editorial-card nutrition-card loading-state" data-testid="nutrition-loading">
          <p className="loading-text">Querying Profile &amp; Nutrition Service (:8001)...</p>
        </div>
      ) : nutritionError && !hasRawNutrition && !hasCachedNutrition ? (
        <div className="editorial-card nutrition-card error-state" data-testid="nutrition-error">
          <p className="error-title">Nutrition Service Unavailable</p>
          <p className="error-text">{nutritionError}</p>
        </div>
      ) : !hasRawNutrition && !hasCachedNutrition ? (
        <div className="editorial-card nutrition-card unavailable-state" data-testid="nutrition-unavailable">
          <p className="unavailable-title">Nutritional data unavailable for this recipe</p>
          <p className="unavailable-text">
            {sourceDataset === 'recipenlg'
              ? 'RecipeNLG records do not contain reported nutrition values, and no USDA composition estimate is currently cached for this ingredient set.'
              : 'Neither source dataset metrics nor cached USDA nutritional estimates are available for this recipe.'}
          </p>
          {onTriggerEstimate && (
            <div className="trigger-estimate-box">
              <button
                type="button"
                className="btn btn-primary trigger-estimate-btn"
                onClick={onTriggerEstimate}
                disabled={isEstimating}
                data-testid="calculate-usda-nutrition-btn"
              >
                {isEstimating ? 'Calculating USDA Nutrition...' : 'Calculate USDA Nutrition'}
              </button>
              {estimateError && (
                <p className="estimate-error-msg" role="alert">
                  {estimateError}
                </p>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="nutrition-cards-container">
          {/* On-demand USDA estimation prompt if raw nutrition exists but cached USDA does not */}
          {!hasCachedNutrition && onTriggerEstimate && (
            <div className="editorial-card trigger-estimate-card" data-testid="usda-estimate-prompt">
              <div className="card-top-row">
                <span className="source-category-tag">USDA SR Legacy Estimation</span>
                <span className="editorial-badge">On-Demand</span>
              </div>
              <p className="unavailable-text">
                No pre-computed USDA nutritional estimate is cached for this recipe. You can calculate an instant composition decomposition using the Profile &amp; Nutrition Service.
              </p>
              <div className="trigger-estimate-box">
                <button
                  type="button"
                  className="btn btn-secondary trigger-estimate-btn"
                  onClick={onTriggerEstimate}
                  disabled={isEstimating}
                  data-testid="calculate-usda-nutrition-btn"
                >
                  {isEstimating ? 'Calculating USDA Nutrition...' : 'Calculate USDA Nutrition'}
                </button>
                {estimateError && (
                  <p className="estimate-error-msg" role="alert">
                    {estimateError}
                  </p>
                )}
              </div>
            </div>
          )}
          {/* 1. Profile Service USDA Estimation (Port 8001) */}
          {hasCachedNutrition && (
            <div
              className="editorial-card usda-nutrition-card"
              data-testid="usda-nutrition-card"
            >
              <div className="card-top-row">
                <span className="source-category-tag">USDA SR Legacy Estimation</span>
                <span
                  className={`editorial-badge status-badge status-${cachedNutrition.status}`}
                  data-testid="nutrition-status-badge"
                >
                  {getStatusLabel(cachedNutrition.status)}
                </span>
              </div>

              {/* Status explanation when uncalculated */}
              {cachedNutrition.status === 'uncalculated' ? (
                <div className="uncalculated-banner" data-testid="uncalculated-banner">
                  <p>
                    Ingredient coverage was insufficient to calculate a reliable USDA nutritional estimate.
                  </p>
                </div>
              ) : (
                <>
                  {/* Coverage row */}
                  {cachedNutrition.ingredient_coverage_pct !== null &&
                    cachedNutrition.ingredient_coverage_pct !== undefined && (
                      <div className="coverage-meta-row" data-testid="nutrition-coverage">
                        <span className="coverage-text">
                          Coverage: {cachedNutrition.ingredient_coverage_pct.toFixed(0)}%
                        </span>
                        {cachedNutrition.mapped_ingredient_count !== null &&
                          cachedNutrition.mapped_ingredient_count !== undefined &&
                          cachedNutrition.total_ingredient_count !== null &&
                          cachedNutrition.total_ingredient_count !== undefined && (
                            <span className="coverage-count">
                              ({cachedNutrition.mapped_ingredient_count} of{' '}
                              {cachedNutrition.total_ingredient_count} ingredients mapped)
                            </span>
                          )}
                      </div>
                    )}

                  {/* Serving Yield Context */}
                  {(cachedNutrition.servings || servings) && (
                    <div className="serving-context-row">
                      <span>
                        Values evaluated per serving (Recipe yield: {cachedNutrition.servings || servings})
                      </span>
                    </div>
                  )}

                  {/* Nutrient Metrics Grid */}
                  <div className="nutrients-grid" data-testid="nutrients-grid">
                    <div className="nutrient-metric-cell" data-testid="metric-calories">
                      <span className="nutrient-label">Calories</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.calories_kcal, 'kcal', 0)}
                      </span>
                    </div>

                    <div className="nutrient-metric-cell" data-testid="metric-protein">
                      <span className="nutrient-label">Protein</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.protein_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-metric-cell" data-testid="metric-carbs">
                      <span className="nutrient-label">Carbohydrates</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.carbohydrates_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-metric-cell" data-testid="metric-fat">
                      <span className="nutrient-label">Total Fat</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.total_fat_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-metric-cell" data-testid="metric-sat-fat">
                      <span className="nutrient-label">Saturated Fat</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.saturated_fat_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-metric-cell" data-testid="metric-fiber">
                      <span className="nutrient-label">Dietary Fiber</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.fiber_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-metric-cell" data-testid="metric-sugar">
                      <span className="nutrient-label">Sugars</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.sugar_g, 'g')}
                      </span>
                    </div>

                    <div className="nutrient-metric-cell" data-testid="metric-sodium">
                      <span className="nutrient-label">Sodium</span>
                      <span className="nutrient-value">
                        {formatMetric(cachedNutrition.sodium_mg, 'mg', 0)}
                      </span>
                    </div>
                  </div>
                </>
              )}

              {/* Provenance note */}
              {cachedNutrition.provenance_note && (
                <p className="provenance-note" data-testid="provenance-note">
                  {cachedNutrition.provenance_note}
                </p>
              )}

              <p className="clinical-disclaimer" data-testid="clinical-disclaimer">
                Nutritional values are mathematical estimates based on ingredient approximations and may vary. Not medical or clinical advice.
              </p>
            </div>
          )}

          {/* 2. Measured / Raw Source Nutrition (Food.com RAW_recipes.csv) */}
          {hasRawNutrition && (
            <div
              className="editorial-card raw-nutrition-card"
              data-testid="raw-nutrition-card"
            >
              <div className="card-top-row">
                <span className="source-category-tag">Source Dataset Reported Metrics</span>
                <span className="editorial-badge source-provenance-badge">Food.com RAW_recipes</span>
              </div>

              <div className="nutrients-grid raw-grid" data-testid="raw-nutrients-grid">
                <div className="nutrient-metric-cell" data-testid="raw-calories">
                  <span className="nutrient-label">Reported Energy</span>
                  <span className="nutrient-value">
                    {formatMetric(rawNutrition.raw_calories, 'kcal', 1)}
                  </span>
                </div>

                <div className="nutrient-metric-cell" data-testid="raw-protein">
                  <span className="nutrient-label">Protein (% DV)</span>
                  <span className="nutrient-value">
                    {formatPercentage(rawNutrition.raw_protein_pdv)}
                  </span>
                </div>

                <div className="nutrient-metric-cell" data-testid="raw-carbs">
                  <span className="nutrient-label">Carbohydrates (% DV)</span>
                  <span className="nutrient-value">
                    {formatPercentage(rawNutrition.raw_carbohydrates_pdv)}
                  </span>
                </div>

                <div className="nutrient-metric-cell" data-testid="raw-fat">
                  <span className="nutrient-label">Total Fat (% DV)</span>
                  <span className="nutrient-value">
                    {formatPercentage(rawNutrition.raw_total_fat_pdv)}
                  </span>
                </div>

                <div className="nutrient-metric-cell" data-testid="raw-sat-fat">
                  <span className="nutrient-label">Saturated Fat (% DV)</span>
                  <span className="nutrient-value">
                    {formatPercentage(rawNutrition.raw_saturated_fat_pdv)}
                  </span>
                </div>

                <div className="nutrient-metric-cell" data-testid="raw-sugar">
                  <span className="nutrient-label">Sugar (% DV)</span>
                  <span className="nutrient-value">
                    {formatPercentage(rawNutrition.raw_sugar_pdv)}
                  </span>
                </div>

                <div className="nutrient-metric-cell" data-testid="raw-sodium">
                  <span className="nutrient-label">Sodium (% DV)</span>
                  <span className="nutrient-value">
                    {formatPercentage(rawNutrition.raw_sodium_pdv)}
                  </span>
                </div>
              </div>

              <p className="raw-note">
                Values reported directly by Food.com contributors as percentage of standard 2,000 calorie Daily Value (%DV).
              </p>
            </div>
          )}
        </div>
      )}

      <style>{`
        .recipe-nutrition-panel {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .section-header-row {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          flex-wrap: wrap;
          gap: var(--space-2);
          padding-bottom: var(--space-2);
          border-bottom: 1px solid var(--color-border);
        }

        .section-heading {
          font-size: var(--text-2xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .nutrition-subtitle {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .nutrition-cards-container {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .nutrition-card {
          padding: var(--space-5);
        }

        .loading-state, .unavailable-state, .error-state {
          padding: var(--space-5);
          border: 1px solid var(--color-border);
          background-color: var(--color-surface);
        }

        .unavailable-title, .error-title {
          font-family: var(--font-serif);
          font-size: var(--text-base);
          font-weight: 600;
          color: var(--color-text-primary);
          margin-bottom: var(--space-1);
        }

        .error-title {
          color: var(--color-error);
        }

        .unavailable-text, .error-text, .loading-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .card-top-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: var(--space-2);
          flex-wrap: wrap;
          margin-bottom: var(--space-3);
          padding-bottom: var(--space-2);
          border-bottom: 1px solid var(--color-border);
        }

        .source-category-tag {
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--color-accent);
        }

        .status-badge {
          font-size: var(--text-xs);
        }

        .status-calculated {
          background-color: var(--color-success-subtle);
          color: var(--color-success);
          border-color: var(--color-success);
        }

        .status-reported_approximate {
          background-color: var(--color-surface-subtle);
          color: var(--color-text-secondary);
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

        .uncalculated-banner {
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          font-size: var(--text-sm);
          color: var(--color-text-muted);
          font-style: italic;
          margin-bottom: var(--space-3);
        }

        .coverage-meta-row {
          display: flex;
          gap: var(--space-2);
          align-items: center;
          font-size: var(--text-xs);
          font-weight: 600;
          color: var(--color-text-secondary);
          margin-bottom: var(--space-3);
        }

        .serving-context-row {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-style: italic;
          margin-bottom: var(--space-3);
        }

        .nutrients-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--space-3);
          margin-bottom: var(--space-4);
        }

        @media (min-width: 640px) {
          .nutrients-grid {
            grid-template-columns: repeat(4, 1fr);
          }
        }

        .nutrient-metric-cell {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
        }

        .nutrient-label {
          font-size: var(--text-xs);
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--color-text-muted);
          font-weight: 600;
        }

        .nutrient-value {
          font-size: var(--text-lg);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .provenance-note {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
          line-height: 1.5;
          margin-bottom: var(--space-2);
          border-left: 2px solid var(--color-border-strong);
          padding-left: var(--space-2);
        }

        .clinical-disclaimer, .raw-note {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          line-height: 1.5;
        }

        .trigger-estimate-box {
          margin-top: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          align-items: flex-start;
        }

        .trigger-estimate-btn {
          font-weight: 600;
        }

        .trigger-estimate-card {
          background-color: var(--color-surface-subtle);
          border: 1px dashed var(--color-border-strong);
          padding: var(--space-5);
        }

        .estimate-error-msg {
          font-size: var(--text-xs);
          color: var(--color-error);
          font-weight: 500;
        }

        .raw-nutrition-card {
          background-color: var(--color-surface);
        }
      `}</style>
    </section>
  );
};

