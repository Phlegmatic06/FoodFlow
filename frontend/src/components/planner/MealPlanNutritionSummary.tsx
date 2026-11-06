import React from 'react';
import { MealPlanDetail } from '../../api/types/planner';

interface MealPlanNutritionSummaryProps {
  plan: MealPlanDetail;
}

export const MealPlanNutritionSummary: React.FC<MealPlanNutritionSummaryProps> = ({ plan }) => {
  const totalSlots = plan.slots.length;
  const avgMealsPerDay = plan.days > 0 ? (totalSlots / plan.days).toFixed(1) : '0';

  return (
    <div className="editorial-card nutrition-summary-card" data-testid="meal-plan-nutrition-summary">
      <div className="summary-header">
        <span className="editorial-badge">Nutritional Architecture &amp; Guidance</span>
        <h3 className="summary-title" data-testid="nutrition-summary-heading">
          Schedule Nutritional Parameters
        </h3>
        <p className="summary-lead">
          Energy constraints and dietary distributions configured for this active meal plan.
        </p>
      </div>

      <div className="metrics-grid">
        <div className="metric-box">
          <span className="metric-label">Daily Calorie Target</span>
          <span className="metric-value" data-testid="nutrition-target-calories">
            {plan.target_calories_kcal ? `${plan.target_calories_kcal} kcal` : 'Unspecified'}
          </span>
          <span className="metric-subtext">
            {plan.target_calories_kcal
              ? 'Calibrated energy boundary'
              : 'Flexible caloric intake'}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Schedule Horizon</span>
          <span className="metric-value" data-testid="nutrition-days-horizon">
            {plan.days} {plan.days === 1 ? 'Day' : 'Days'}
          </span>
          <span className="metric-subtext">Continuous planning period</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Total Planned Meals</span>
          <span className="metric-value" data-testid="nutrition-total-meals">
            {totalSlots} Meals
          </span>
          <span className="metric-subtext">{avgMealsPerDay} meals / day average</span>
        </div>
      </div>

      <div className="disclosure-box" data-testid="nutrition-disclosure-box">
        <span className="editorial-badge disclosure-badge">Nutrition Disclosure</span>
        <p className="disclosure-text">
          <strong>Macronutrient Distribution Note:</strong> FoodFlow schedules meals around individualized
          energy targets and dietary preferences. Exact macronutrient totals (protein, carbohydrates, fat)
          are computed and displayed when complete nutritional data is available from the USDA SR Legacy
          and recipe catalogue. Missing recipe nutrition values are transparently indicated as &ldquo;Unavailable&rdquo;
          rather than estimated or fabricated.
        </p>
      </div>

      <style>{`
        .nutrition-summary-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-5);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          padding: var(--space-6);
        }

        .summary-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .summary-title {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          margin: 0;
        }

        .summary-lead {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          margin: 0;
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: var(--space-4);
        }

        .metric-box {
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          background: var(--color-surface);
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .metric-label {
          font-size: var(--text-xs);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
        }

        .metric-value {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
        }

        .metric-subtext {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .disclosure-box {
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          border-left: 4px solid var(--color-text);
          border-radius: 0px !important;
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .disclosure-badge {
          background: var(--color-text);
          color: var(--color-bg);
          align-self: flex-start;
          font-size: 10px;
        }

        .disclosure-text {
          font-size: var(--text-xs);
          color: var(--color-text);
          margin: 0;
          line-height: 1.45;
        }
      `}</style>
    </div>
  );
};

