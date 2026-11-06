import React, { useState, useCallback } from 'react';
import { profileClient } from '../../api/profileClient';
import {
  ActivityLevel,
  BiologicalSex,
  BiometricsCalculationRequest,
  BiometricsCalculationResponse,
  NutritionGoal,
} from '../../api/types/profile';

interface BiometricsCalculatorProps {
  onCalculationResult?: (result: BiometricsCalculationResponse | null) => void;
}

export const BiometricsCalculator: React.FC<BiometricsCalculatorProps> = ({
  onCalculationResult,
}) => {
  // Purely in-memory React state (no localStorage / cookies for user privacy)
  const [age, setAge] = useState<string>('');
  const [sex, setSex] = useState<string>(''); // '' | 'male' | 'female'
  const [height, setHeight] = useState<string>('');
  const [weight, setWeight] = useState<string>('');
  const [activityLevel, setActivityLevel] = useState<ActivityLevel>('moderately_active');
  const [goal, setGoal] = useState<NutritionGoal>('maintain');

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<BiometricsCalculationResponse | null>(null);

  const handleClear = useCallback(() => {
    setAge('');
    setSex('');
    setHeight('');
    setWeight('');
    setActivityLevel('moderately_active');
    setGoal('maintain');
    setValidationError(null);
    setApiError(null);
    setResult(null);
    if (onCalculationResult) {
      onCalculationResult(null);
    }
  }, [onCalculationResult]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setApiError(null);

    // Validation
    const ageNum = parseInt(age, 10);
    const heightNum = parseFloat(height);
    const weightNum = parseFloat(weight);

    if (isNaN(ageNum) || ageNum < 1 || ageNum > 120) {
      setValidationError('Please enter a valid age between 1 and 120 years.');
      return;
    }
    if (isNaN(heightNum) || heightNum < 50.0 || heightNum > 300.0) {
      setValidationError('Please enter a valid height between 50 and 300 cm.');
      return;
    }
    if (isNaN(weightNum) || weightNum < 20.0 || weightNum > 500.0) {
      setValidationError('Please enter a valid weight between 20 and 500 kg.');
      return;
    }

    const payload: BiometricsCalculationRequest = {
      age_years: ageNum,
      height_cm: heightNum,
      weight_kg: weightNum,
      activity_level: activityLevel,
      goal: goal,
    };

    if (sex === 'male' || sex === 'female') {
      payload.sex_for_equation = sex as BiologicalSex;
    } else {
      payload.sex_for_equation = null;
    }

    setIsLoading(true);
    try {
      const response = await profileClient.calculateBiometrics(payload);
      setResult(response);
      if (onCalculationResult) {
        onCalculationResult(response);
      }
    } catch (err: unknown) {
      setApiError(
        err instanceof Error ? err.message : 'An error occurred while calculating biometrics.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  const formatBmiCategory = (cat: string) => {
    switch (cat) {
      case 'underweight':
        return 'Underweight (< 18.5)';
      case 'normal_weight':
        return 'Normal Weight (18.5–24.9)';
      case 'overweight':
        return 'Overweight (25.0–29.9)';
      case 'obesity_class_1':
        return 'Obesity Class I (30.0–34.9)';
      case 'obesity_class_2':
        return 'Obesity Class II (35.0–39.9)';
      case 'obesity_class_3':
        return 'Obesity Class III (≥ 40.0)';
      default:
        return cat.replace(/_/g, ' ');
    }
  };

  return (
    <section className="biometrics-calculator-section" data-testid="biometrics-calculator-section">
      <div className="section-header-block">
        <span className="editorial-badge">Metabolic Engine</span>
        <h2 className="section-title" data-testid="calculator-heading">
          Daily Nutrition &amp; Biometrics Calculator
        </h2>
        <p className="section-lead">
          Evaluate Body Mass Index (BMI), Basal Metabolic Rate (clinical equation standard), and Total
          Daily Energy Expenditure (TDEE). Biometrics are completely optional and kept strictly in
          temporary memory.
        </p>
      </div>

      <div className="calculator-layout-grid">
        {/* Form Column */}
        <form
          className="editorial-card calculator-form"
          onSubmit={handleSubmit}
          data-testid="biometrics-form"
          noValidate
        >
          <div className="form-row two-col">
            <div className="form-group">
              <label htmlFor="bio-age" className="form-label">
                Age <span className="unit-label">(years)</span> *
              </label>
              <input
                id="bio-age"
                type="number"
                min="1"
                max="120"
                className="form-input"
                placeholder="e.g. 28"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                required
                data-testid="input-age"
              />
            </div>

            <div className="form-group">
              <label htmlFor="bio-sex" className="form-label">
                Biological Sex <span className="optional-tag">(Optional)</span>
              </label>
              <select
                id="bio-sex"
                className="form-select"
                value={sex}
                onChange={(e) => setSex(e.target.value)}
                data-testid="select-sex"
              >
                <option value="">Omit (Calculates BMI only)</option>
                <option value="male">Male (Mifflin constant +5)</option>
                <option value="female">Female (Mifflin constant -161)</option>
              </select>
              <span className="field-hint">Required only for sex-specific metabolic rate constants.</span>
            </div>
          </div>

          <div className="form-row two-col">
            <div className="form-group">
              <label htmlFor="bio-height" className="form-label">
                Height <span className="unit-label">(cm)</span> *
              </label>
              <input
                id="bio-height"
                type="number"
                step="0.1"
                min="50"
                max="300"
                className="form-input"
                placeholder="e.g. 175"
                value={height}
                onChange={(e) => setHeight(e.target.value)}
                required
                data-testid="input-height"
              />
            </div>

            <div className="form-group">
              <label htmlFor="bio-weight" className="form-label">
                Weight <span className="unit-label">(kg)</span> *
              </label>
              <input
                id="bio-weight"
                type="number"
                step="0.1"
                min="20"
                max="500"
                className="form-input"
                placeholder="e.g. 70"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                required
                data-testid="input-weight"
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="bio-activity" className="form-label">
              Physical Activity Level *
            </label>
            <select
              id="bio-activity"
              className="form-select"
              value={activityLevel}
              onChange={(e) => setActivityLevel(e.target.value as ActivityLevel)}
              data-testid="select-activity"
            >
              <option value="sedentary">Sedentary (Little or no exercise, desk work — factor 1.20)</option>
              <option value="lightly_active">Lightly Active (Light exercise 1–3 days/week — factor 1.375)</option>
              <option value="moderately_active">Moderately Active (Moderate exercise 3–5 days/week — factor 1.55)</option>
              <option value="very_active">Very Active (Hard exercise 6–7 days/week — factor 1.725)</option>
              <option value="extra_active">Extra Active (Very intense daily physical training — factor 1.90)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="bio-goal" className="form-label">
              Weight Management Goal *
            </label>
            <select
              id="bio-goal"
              className="form-select"
              value={goal}
              onChange={(e) => setGoal(e.target.value as NutritionGoal)}
              data-testid="select-goal"
            >
              <option value="maintain">Maintain Current Weight (0 kcal shift)</option>
              <option value="lose">Sustainable Weight Loss (-400 kcal/day)</option>
              <option value="gain">Controlled Muscle Gain (+400 kcal/day)</option>
            </select>
          </div>

          {validationError && (
            <div className="error-alert" role="alert" data-testid="calculator-validation-error">
              <span>{validationError}</span>
            </div>
          )}

          {apiError && (
            <div className="error-alert" role="alert" data-testid="calculator-api-error">
              <span>{apiError}</span>
            </div>
          )}

          <div className="form-actions">
            <button
              type="submit"
              className="btn btn-primary btn-submit-bio"
              disabled={isLoading}
              data-testid="submit-biometrics-btn"
            >
              {isLoading ? 'Computing Target...' : 'Calculate Targets →'}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-clear-bio"
              onClick={handleClear}
              data-testid="clear-biometrics-btn"
            >
              Clear Form
            </button>
          </div>

          <div className="privacy-badge-row">
            <span className="editorial-badge privacy-badge">Guest Session Private</span>
            <span className="privacy-note">Zero disk persistence. Metrics discarded on page refresh.</span>
          </div>
        </form>

        {/* Results Column */}
        <div className="calculator-results-pane" data-testid="calculator-results-pane">
          {!result ? (
            <div className="editorial-card results-empty-card" data-testid="results-empty-state">
              <span className="editorial-badge">Awaiting Input</span>
              <h3 className="empty-title">No Biometrics Submitted</h3>
              <p className="empty-text">
                Enter your physical parameters on the left to compute your personalized BMI, Basal
                Metabolic Rate (BMR), Total Daily Energy Expenditure (TDEE), and AMDR target breakdown.
              </p>
              <div className="sample-tip">
                <span className="tip-label">Did you know?</span>
                <p className="tip-text">
                  Omitting biological sex calculates Body Mass Index without fabricating metabolic rates.
                </p>
              </div>
            </div>
          ) : (
            <div className="editorial-card results-active-card" data-testid="results-active-card">
              <div className="results-top-strip">
                <span className="editorial-badge results-badge">Calculated Evaluation</span>
                <span className="equation-tag">Mifflin Equation (1990)</span>
              </div>

              {/* Metrics Grid */}
              <div className="metrics-grid">
                {/* BMI Card */}
                <div className="metric-box" data-testid="metric-bmi-box">
                  <span className="metric-label">Body Mass Index</span>
                  <span className="metric-value" data-testid="result-bmi">
                    {result.bmi} <span className="metric-unit">kg/m²</span>
                  </span>
                  <span className="category-pill" data-testid="result-bmi-category">
                    {formatBmiCategory(result.bmi_category)}
                  </span>
                </div>

                {/* BMR Card */}
                <div className="metric-box" data-testid="metric-bmr-box">
                  <span className="metric-label">Basal Metabolic Rate (BMR)</span>
                  <span className="metric-value" data-testid="result-bmr">
                    {result.bmr_kcal !== null ? (
                      <>
                        {result.bmr_kcal} <span className="metric-unit">kcal/day</span>
                      </>
                    ) : (
                      <span className="unavailable-value">Not calculated (sex omitted)</span>
                    )}
                  </span>
                  <span className="metric-note">Energy expended at complete physical rest</span>
                </div>

                {/* TDEE Card */}
                <div className="metric-box" data-testid="metric-tdee-box">
                  <span className="metric-label">Total Daily Energy (TDEE)</span>
                  <span className="metric-value" data-testid="result-tdee">
                    {result.tdee_kcal !== null ? (
                      <>
                        {result.tdee_kcal} <span className="metric-unit">kcal/day</span>
                      </>
                    ) : (
                      <span className="unavailable-value">Not calculated</span>
                    )}
                  </span>
                  <span className="metric-note">
                    {result.activity_multiplier
                      ? `Applied factor ${result.activity_multiplier} (${result.activity_multiplier >= 1.55 ? 'Active' : 'Moderate'})`
                      : 'Activity factor unavailable'}
                  </span>
                </div>

                {/* Target Calories */}
                <div className="metric-box highlight-box" data-testid="metric-target-box">
                  <span className="metric-label">Recommended Caloric Target</span>
                  <span className="metric-value highlight-value" data-testid="result-target-calories">
                    {result.target_calories_kcal !== null ? (
                      <>
                        {result.target_calories_kcal} <span className="metric-unit">kcal/day</span>
                      </>
                    ) : (
                      <span className="unavailable-value">Not calculated</span>
                    )}
                  </span>
                  <span className="metric-note">
                    {result.goal_adjustment_kcal !== null
                      ? `Adjusted for goal: ${result.goal_adjustment_kcal > 0 ? '+' : ''}${result.goal_adjustment_kcal} kcal/day`
                      : 'Goal adjustment unavailable'}
                  </span>
                </div>
              </div>

              {/* Caveats */}
              {result.caveats && result.caveats.length > 0 && (
                <div className="caveats-box" data-testid="results-caveats">
                  <h4 className="caveats-heading">Clinical Caveats &amp; Method Notes:</h4>
                  <ul className="caveats-list">
                    {result.caveats.map((c, idx) => (
                      <li key={idx}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Advisory Disclaimer */}
              <p className="clinical-disclaimer" data-testid="results-disclaimer">
                {result.disclaimer}
              </p>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .biometrics-calculator-section {
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
          color: var(--color-text-primary);
        }

        .section-lead {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          max-width: 800px;
          line-height: 1.6;
        }

        .calculator-layout-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-6);
        }

        @media (min-width: 900px) {
          .calculator-layout-grid {
            grid-template-columns: 1.1fr 1fr;
          }
        }

        .calculator-form {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          background-color: var(--color-surface);
        }

        .form-row.two-col {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-4);
        }

        @media (min-width: 600px) {
          .form-row.two-col {
            grid-template-columns: 1fr 1fr;
          }
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

        .unit-label {
          font-weight: 400;
          color: var(--color-text-muted);
          text-transform: none;
        }

        .optional-tag {
          font-size: 0.7rem;
          color: var(--color-text-muted);
          text-transform: uppercase;
        }

        .form-input, .form-select {
          padding: var(--space-2) var(--space-3);
          border: 1px solid var(--color-border-strong);
          background-color: var(--color-bg);
          color: var(--color-text-primary);
          font-size: var(--text-sm);
        }

        .form-input:focus, .form-select:focus {
          outline: 2px solid var(--color-focus);
          outline-offset: 1px;
        }

        .field-hint {
          font-size: 0.72rem;
          color: var(--color-text-muted);
          line-height: 1.3;
        }

        .error-alert {
          padding: var(--space-2) var(--space-3);
          background-color: var(--color-error-subtle);
          border: 1px solid var(--color-error);
          color: var(--color-error);
          font-size: var(--text-xs);
          font-weight: 600;
        }

        .form-actions {
          display: flex;
          gap: var(--space-3);
          margin-top: var(--space-2);
        }

        .btn-submit-bio {
          flex: 1;
        }

        .privacy-badge-row {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          padding-top: var(--space-3);
          border-top: 1px solid var(--color-border);
        }

        .privacy-badge {
          background-color: var(--color-secondary-subtle);
          color: var(--color-secondary-accent);
          font-size: 0.65rem;
        }

        .privacy-note {
          font-size: 0.72rem;
          color: var(--color-text-muted);
        }

        /* Results Pane */
        .results-empty-card, .results-active-card {
          height: 100%;
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          background-color: var(--color-surface);
        }

        .empty-title {
          font-size: var(--text-lg);
          font-family: var(--font-serif);
        }

        .empty-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          line-height: 1.6;
        }

        .sample-tip {
          margin-top: auto;
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
        }

        .tip-label {
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          color: var(--color-accent);
          display: block;
          margin-bottom: var(--space-1);
        }

        .tip-text {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .results-top-strip {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-2);
        }

        .equation-tag {
          font-size: var(--text-xs);
          font-family: var(--font-mono);
          color: var(--color-text-muted);
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: var(--space-3);
        }

        .metric-box {
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .highlight-box {
          grid-column: span 2;
          background-color: var(--color-accent-subtle);
          border-color: var(--color-accent);
        }

        .metric-label {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-muted);
          font-weight: 700;
        }

        .metric-value {
          font-size: var(--text-xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .highlight-value {
          color: var(--color-accent);
          font-size: var(--text-2xl);
        }

        .metric-unit {
          font-size: var(--text-xs);
          font-weight: 500;
          color: var(--color-text-secondary);
        }

        .unavailable-value {
          font-size: var(--text-sm);
          color: var(--color-text-muted);
          font-style: italic;
          font-weight: 400;
        }

        .category-pill {
          font-size: 0.72rem;
          color: var(--color-secondary-accent);
          font-weight: 600;
        }

        .metric-note {
          font-size: 0.7rem;
          color: var(--color-text-muted);
        }

        .caveats-box {
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border-left: 2px solid var(--color-accent);
        }

        .caveats-heading {
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          margin-bottom: var(--space-1);
        }

        .caveats-list {
          padding-left: var(--space-4);
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
          line-height: 1.5;
        }

        .clinical-disclaimer {
          font-size: 0.72rem;
          color: var(--color-text-muted);
          line-height: 1.5;
        }
      `}</style>
    </section>
  );
};
