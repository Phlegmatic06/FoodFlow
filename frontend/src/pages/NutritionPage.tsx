import React, { useState } from 'react';
import { BiometricsCalculationResponse } from '../api/types/profile';
import { BiometricsCalculator } from '../components/nutrition/BiometricsCalculator';
import { MacroTargetsPanel } from '../components/nutrition/MacroTargetsPanel';
import { USDAFoodExplorer } from '../components/nutrition/USDAFoodExplorer';
import { RecipeNutritionEstimator } from '../components/nutrition/RecipeNutritionEstimator';

export const NutritionPage: React.FC = () => {
  // In-memory state for biometrics calculation result (NEVER persisted to localStorage or sessionStorage)
  const [biometricsResult, setBiometricsResult] = useState<BiometricsCalculationResponse | null>(null);

  return (
    <div className="container page-container" data-testid="nutrition-page">
      {/* 1. Page Header */}
      <header className="page-header">
        <span className="editorial-badge">Profile &amp; Nutrition Service :8001</span>
        <h1 className="page-title">Biometric Profiling &amp; USDA Nutritional Science</h1>
        <p className="page-lead">
          Calculate basal metabolic rate (BMR) via the Mifflin-St Jeor clinical standard, derive total daily
          energy expenditure (TDEE), configure AMDR macronutrient targets, and explore the USDA SR Legacy
          nutritional database with recipe nutrient decomposition.
        </p>
      </header>

      {/* 2. Biometric Calculator & Macro Targets Workspace */}
      <section className="nutrition-workspace-section" aria-labelledby="biometrics-section-heading">
        <div className="section-title-wrap">
          <span className="editorial-badge">Metabolic Profile</span>
          <h2 id="biometrics-section-heading" className="section-title">
            Biometric Profiling &amp; Energy Needs
          </h2>
          <p className="section-desc">
            Enter physical parameters to derive energy expenditure and macronutrient distributions in real time.
            All biometric data is evaluated in memory and is never persisted to disk or sent with user identifiers.
          </p>
        </div>

        <div className="biometrics-macro-grid">
          <BiometricsCalculator onCalculationResult={setBiometricsResult} />
          <MacroTargetsPanel biometricsResult={biometricsResult} calculation={biometricsResult} />
        </div>
      </section>

      {/* 3. USDA Food Database Explorer */}
      <section className="nutrition-workspace-section" aria-labelledby="usda-section-heading">
        <div className="section-title-wrap">
          <span className="editorial-badge">Ground Truth Database</span>
          <h2 id="usda-section-heading" className="section-title">
            USDA SR Legacy Food Composition Explorer
          </h2>
          <p className="section-desc">
            Direct analytical query access to 7,793 standardized food items and over 660,000 laboratory-measured
            nutrient data points. Inspect nutritional composition per 100 grams and view empirical household portion gram weights.
          </p>
        </div>

        <USDAFoodExplorer />
      </section>

      {/* 4. Recipe Nutritional Decomposition & Estimator */}
      <section className="nutrition-workspace-section" aria-labelledby="recipe-estimator-heading">
        <div className="section-title-wrap">
          <span className="editorial-badge">Ingredient Aggregation</span>
          <h2 id="recipe-estimator-heading" className="section-title">
            Recipe Nutrition Estimator &amp; Decomposition
          </h2>
          <p className="section-desc">
            Evaluate recipes from the catalogue against canonical USDA ingredient mappings to compute comprehensive
            per-serving macro and micronutrient totals, with ingredient coverage transparency and unmapped ingredient warnings.
          </p>
        </div>

        <RecipeNutritionEstimator />
      </section>

      {/* 5. Clinical & Academic Disclaimer */}
      <div className="editorial-card disclaimer-card" data-testid="clinical-disclaimer-card">
        <span className="editorial-badge">Nutritional Advisory</span>
        <h3 className="disclaimer-heading">Clinical Scope &amp; Regulatory Notice</h3>
        <p className="disclaimer-text">
          These calculated estimates and nutritional analyses are provided strictly for educational and
          informational purposes within this academic software engineering capstone. They do not constitute
          medical diagnosis, clinical advice, or individualized nutritional prescription. Consult a licensed
          physician or registered dietitian before making significant dietary interventions.
        </p>
      </div>

      <style>{`
        .page-container {
          padding-top: var(--space-8);
          padding-bottom: var(--space-12);
          display: flex;
          flex-direction: column;
          gap: var(--space-10);
        }

        .page-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          border-bottom: 2px solid var(--color-border-strong);
          padding-bottom: var(--space-6);
        }

        .page-title {
          font-size: var(--text-3xl);
          font-family: var(--font-serif);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .page-lead {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
          max-width: 820px;
          line-height: 1.6;
        }

        .nutrition-workspace-section {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }

        .section-title-wrap {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .section-title {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .section-desc {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          max-width: 800px;
          line-height: 1.5;
        }

        .biometrics-macro-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-8);
          align-items: start;
        }

        @media (min-width: 900px) {
          .biometrics-macro-grid {
            grid-template-columns: 1fr 1fr;
          }
        }

        .disclaimer-card {
          background-color: var(--color-surface-subtle);
          border-left: 4px solid var(--color-border-strong);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          padding: var(--space-5);
        }

        .disclaimer-heading {
          font-size: var(--text-base);
          font-family: var(--font-serif);
          margin-top: var(--space-2);
        }

        .disclaimer-text {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          line-height: 1.6;
        }
      `}</style>
    </div>
  );
};
