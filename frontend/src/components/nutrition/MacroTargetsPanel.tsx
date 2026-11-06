import React from 'react';
import { BiometricsCalculationResponse } from '../../api/types/profile';

interface MacroTargetsPanelProps {
  biometricsResult?: BiometricsCalculationResponse | null;
  calculation?: BiometricsCalculationResponse | null;
}

export const MacroTargetsPanel: React.FC<MacroTargetsPanelProps> = ({
  biometricsResult,
  calculation,
}) => {
  const activeResult = biometricsResult || calculation;
  const macros = activeResult?.macro_targets_grams;
  const targetCalories = activeResult?.target_calories_kcal;

  // Authoritative baseline distribution
  const defaultProteinPct = 20;
  const defaultCarbsPct = 50;
  const defaultFatPct = 30;

  // Compute energy contributions if grams are available
  const proteinKcal = macros ? macros.protein_g * 4 : null;
  const carbsKcal = macros ? macros.carbohydrates_g * 4 : null;
  const fatKcal = macros ? macros.fat_g * 9 : null;

  return (
    <section className="macro-targets-section" data-testid="macro-targets-panel">
      <div className="section-header-block">
        <span className="editorial-badge">Macronutrient Framework</span>
        <h2 className="section-title" data-testid="macro-heading">
          Target Macronutrient Distribution (AMDR 20 / 50 / 30)
        </h2>
        <p className="section-lead">
          FoodFlow utilizes the Acceptable Macronutrient Distribution Range (AMDR) calibrated for
          sustainable metabolic balance: 20% protein (4 kcal/g), 50% carbohydrates (4 kcal/g), and
          30% dietary fats (9 kcal/g).
        </p>
      </div>

      <div className="editorial-card macro-main-card" data-testid="macro-main-card">
        {/* Top Summary Bar */}
        <div className="macro-summary-strip">
          <div className="summary-item">
            <span className="summary-label">Target Energy Intake</span>
            <span className="summary-value" data-testid="macro-target-calories">
              {targetCalories !== null && targetCalories !== undefined ? (
                <>
                  {targetCalories} <span className="summary-unit">kcal / day</span>
                </>
              ) : (
                <span className="summary-placeholder">Awaiting Biometrics</span>
              )}
            </span>
          </div>

          <div className="summary-item">
            <span className="summary-label">Standard AMDR Ratio</span>
            <span className="summary-value ratio-value" data-testid="macro-ratio-split">
              20% P &bull; 50% C &bull; 30% F
            </span>
          </div>
        </div>

        {/* Visual Distribution Bar */}
        <div className="macro-bar-container" aria-label="Macronutrient distribution bar">
          <div
            className="macro-bar-segment segment-protein"
            style={{ width: `${defaultProteinPct}%` }}
            title="Protein: 20%"
            data-testid="macro-bar-protein"
          >
            <span>Protein 20%</span>
          </div>
          <div
            className="macro-bar-segment segment-carbs"
            style={{ width: `${defaultCarbsPct}%` }}
            title="Carbohydrates: 50%"
            data-testid="macro-bar-carbs"
          >
            <span>Carbohydrates 50%</span>
          </div>
          <div
            className="macro-bar-segment segment-fat"
            style={{ width: `${defaultFatPct}%` }}
            title="Fat: 30%"
            data-testid="macro-bar-fat"
          >
            <span>Fat 30%</span>
          </div>
        </div>

        {/* Macro Columns */}
        <div className="macro-cards-grid">
          {/* Protein */}
          <div className="macro-card protein-card" data-testid="card-protein">
            <div className="card-top">
              <span className="macro-name">Protein</span>
              <span className="macro-pct-badge">20% Energy</span>
            </div>
            <div className="macro-grams-row">
              <span className="macro-grams" data-testid="protein-grams">
                {macros ? `${macros.protein_g}g` : '—'}
              </span>
              {proteinKcal !== null && (
                <span className="macro-kcal-equiv" data-testid="protein-kcal">
                  ~{proteinKcal} kcal
                </span>
              )}
            </div>
            <div className="macro-footer-meta">
              <span className="meta-factor">Standard: 4.0 kcal / g</span>
              <span className="meta-range">AMDR Range: 10%–35%</span>
            </div>
          </div>

          {/* Carbohydrates */}
          <div className="macro-card carbs-card" data-testid="card-carbs">
            <div className="card-top">
              <span className="macro-name">Carbohydrates</span>
              <span className="macro-pct-badge">50% Energy</span>
            </div>
            <div className="macro-grams-row">
              <span className="macro-grams" data-testid="carbs-grams">
                {macros ? `${macros.carbohydrates_g}g` : '—'}
              </span>
              {carbsKcal !== null && (
                <span className="macro-kcal-equiv" data-testid="carbs-kcal">
                  ~{carbsKcal} kcal
                </span>
              )}
            </div>
            <div className="macro-footer-meta">
              <span className="meta-factor">Standard: 4.0 kcal / g</span>
              <span className="meta-range">AMDR Range: 45%–65%</span>
            </div>
          </div>

          {/* Fat */}
          <div className="macro-card fat-card" data-testid="card-fat">
            <div className="card-top">
              <span className="macro-name">Dietary Fat</span>
              <span className="macro-pct-badge">30% Energy</span>
            </div>
            <div className="macro-grams-row">
              <span className="macro-grams" data-testid="fat-grams">
                {macros ? `${macros.fat_g}g` : '—'}
              </span>
              {fatKcal !== null && (
                <span className="macro-kcal-equiv" data-testid="fat-kcal">
                  ~{fatKcal} kcal
                </span>
              )}
            </div>
            <div className="macro-footer-meta">
              <span className="meta-factor">Standard: 9.0 kcal / g</span>
              <span className="meta-range">AMDR Range: 20%–35%</span>
            </div>
          </div>
        </div>

        {!macros && (
          <div className="macro-guidance-note" data-testid="macro-guidance-note">
            <p>
              Submit your biometrics with biological sex specified in the calculator above to
              populate personal target gram values based on your daily energy expenditure.
            </p>
          </div>
        )}
      </div>

      <style>{`
        .macro-targets-section {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .macro-main-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
          background-color: var(--color-surface);
        }

        .macro-summary-strip {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          flex-wrap: wrap;
          gap: var(--space-4);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-4);
        }

        .summary-item {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .summary-label {
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-muted);
        }

        .summary-value {
          font-size: var(--text-2xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .summary-unit {
          font-size: var(--text-sm);
          font-weight: 500;
          color: var(--color-text-secondary);
        }

        .summary-placeholder {
          font-size: var(--text-base);
          font-weight: 500;
          color: var(--color-text-muted);
          font-style: italic;
        }

        .ratio-value {
          font-family: var(--font-mono);
          font-size: var(--text-base);
          color: var(--color-accent);
        }

        /* Distribution Bar */
        .macro-bar-container {
          display: flex;
          height: 32px;
          border: 1px solid var(--color-border-strong);
          overflow: hidden;
        }

        .macro-bar-segment {
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.72rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: #ffffff;
        }

        .segment-protein {
          background-color: #8F3A24; /* Terracotta / Rust */
        }

        .segment-carbs {
          background-color: #C28B38; /* Ochre / Harvest Gold */
        }

        .segment-fat {
          background-color: #3E5442; /* Deep Sage Forest */
        }

        /* 3-Column Macro Grid */
        .macro-cards-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-4);
        }

        @media (min-width: 768px) {
          .macro-cards-grid {
            grid-template-columns: repeat(3, 1fr);
          }
        }

        .macro-card {
          padding: var(--space-4);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .protein-card {
          border-top: 4px solid #8F3A24;
        }

        .carbs-card {
          border-top: 4px solid #C28B38;
        }

        .fat-card {
          border-top: 4px solid #3E5442;
        }

        .card-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .macro-name {
          font-size: var(--text-base);
          font-family: var(--font-serif);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .macro-pct-badge {
          font-size: 0.68rem;
          font-weight: 700;
          text-transform: uppercase;
          padding: 0.15rem 0.4rem;
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          color: var(--color-text-secondary);
        }

        .macro-grams-row {
          display: flex;
          align-items: baseline;
          gap: var(--space-2);
        }

        .macro-grams {
          font-size: var(--text-3xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .macro-kcal-equiv {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-family: var(--font-mono);
        }

        .macro-footer-meta {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          border-top: 1px solid var(--color-border);
          padding-top: var(--space-2);
          font-size: 0.72rem;
          color: var(--color-text-muted);
        }

        .macro-guidance-note {
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border-left: 2px solid var(--color-border-strong);
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }
      `}</style>
    </section>
  );
};

