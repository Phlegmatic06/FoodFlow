import React, { useState } from 'react';
import {
  GeneratedMealPlanResponse,
  GenerateMealPlanRequest,
  MealPlanSlotInput,
  MealSlotType,
  SaveMealPlanRequest,
} from '../../api/types/planner';
import { plannerClient } from '../../api/plannerClient';

interface MealPlanGeneratorProps {
  onSavePlan: (planRequest: SaveMealPlanRequest) => Promise<void>;
  isSaving: boolean;
  onCancel?: () => void;
  initialTargetCalories?: number | null;
}

const AVAILABLE_SLOTS: { id: MealSlotType; label: string }[] = [
  { id: 'breakfast', label: 'Breakfast' },
  { id: 'lunch', label: 'Lunch' },
  { id: 'dinner', label: 'Dinner' },
  { id: 'snack', label: 'Snack' },
];

const DIET_OPTIONS = [
  { value: '', label: 'No Diet Restrictions' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'pescatarian', label: 'Pescatarian' },
  { value: 'gluten-free', label: 'Gluten-Free' },
  { value: 'dairy-free', label: 'Dairy-Free' },
  { value: 'keto', label: 'Keto' },
];

const CUISINE_OPTIONS = [
  { value: '', label: 'All Cuisines' },
  { value: 'Italian', label: 'Italian' },
  { value: 'Mexican', label: 'Mexican' },
  { value: 'Asian', label: 'Asian' },
  { value: 'American', label: 'American' },
  { value: 'Mediterranean', label: 'Mediterranean' },
  { value: 'Indian', label: 'Indian' },
  { value: 'French', label: 'French' },
];

export const MealPlanGenerator: React.FC<MealPlanGeneratorProps> = ({
  onSavePlan,
  isSaving,
  onCancel,
  initialTargetCalories,
}) => {
  const [days, setDays] = useState<number | string>(7);
  const [selectedSlots, setSelectedSlots] = useState<MealSlotType[]>(['breakfast', 'lunch', 'dinner']);
  const [targetCalories, setTargetCalories] = useState<string>(
    initialTargetCalories ? String(initialTargetCalories) : ''
  );
  const [diet, setDiet] = useState<string>('');
  const [cuisine, setCuisine] = useState<string>('');
  const [maxTime, setMaxTime] = useState<string>('');

  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<GeneratedMealPlanResponse | null>(null);
  const [planName, setPlanName] = useState<string>('Weekly Meal Schedule (7 Days)');

  const toggleSlot = (slot: MealSlotType) => {
    if (selectedSlots.includes(slot)) {
      if (selectedSlots.length === 1) return; // Prevent empty slots
      setSelectedSlots(selectedSlots.filter((s) => s !== slot));
    } else {
      setSelectedSlots([...selectedSlots, slot]);
    }
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    setGenError(null);

    // Validation
    const numDays = Number(days);
    if (isNaN(numDays) || numDays < 1 || numDays > 14) {
      setGenError('Planning horizon must be between 1 and 14 days.');
      return;
    }
    if (selectedSlots.length === 0) {
      setGenError('Select at least one daily meal slot.');
      return;
    }
    const calNum = targetCalories.trim() ? Number(targetCalories) : null;
    if (calNum !== null && (isNaN(calNum) || calNum < 800 || calNum > 6000)) {
      setGenError('Daily calorie target must be between 800 and 6,000 kcal.');
      return;
    }

    const payload: GenerateMealPlanRequest = {
      days: numDays,
      slots: selectedSlots,
      target_calories_kcal: calNum,
      diet_preference: diet ? diet : null,
      cuisine_preference: cuisine ? cuisine : null,
      max_time_per_recipe: maxTime.trim() ? Number(maxTime) : null,
    };

    setIsGenerating(true);
    try {
      const res = await plannerClient.generateMealPlan(payload);
      setProposal(res);
      setPlanName(`Weekly Meal Schedule (${numDays} Days)`);
    } catch (err: unknown) {
      setGenError(
        err instanceof Error ? err.message : 'Failed to generate meal plan proposal from backend.'
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const handleConfirmSave = async () => {
    if (!proposal) return;
    const slotsPayload: MealPlanSlotInput[] = [];

    proposal.days.forEach((day) => {
      day.slots.forEach((slot) => {
        slotsPayload.push({
          day_index: day.day_index,
          slot_type: slot.slot_type,
          recipe_id: slot.recipe_id,
          recipe_title: slot.title,
        });
      });
    });

    const saveRequest: SaveMealPlanRequest = {
      name: planName.trim() || `Meal Schedule (${proposal.days.length} Days)`,
      days: proposal.days.length,
      target_calories_kcal: proposal.target_calories_kcal ?? null,
      slots: slotsPayload,
    };

    await onSavePlan(saveRequest);
  };

  return (
    <div className="editorial-card generator-card" data-testid="meal-plan-generator-card">
      <div className="generator-header">
        <span className="editorial-badge">Recommendation Engine</span>
        <h2 className="generator-title" data-testid="generator-title">
          {proposal ? 'Review Generated Meal Plan Proposal' : 'Generate Automated Meal Plan'}
        </h2>
        <p className="generator-desc">
          {proposal
            ? 'Inspect suggested recipes and estimated calories before saving to your persistent guest session.'
            : 'Configure your planning horizon, meal slots, and preferences. The planner service balances recipe variety across your week.'}
        </p>
      </div>

      {genError && (
        <div className="status-box error-box" role="alert" data-testid="generator-error-banner">
          <span className="editorial-badge error-badge">Generation Notice</span>
          <p className="error-text">{genError}</p>
        </div>
      )}

      {!proposal ? (
        <form noValidate onSubmit={handleGenerate} className="generator-form" data-testid="generator-form">
          <div className="form-row days-slots-row">
            <div className="form-group days-group">
              <label htmlFor="gen-days" className="field-label">
                Planning Horizon (Days: 1–14)
              </label>
              <input
                id="gen-days"
                type="number"
                min={1}
                max={14}
                value={days}
                onChange={(e) => setDays(e.target.value)}
                className="input-field"
                disabled={isGenerating}
                data-testid="gen-days-input"
                required
              />
              <span className="field-hint">Default 7 days for a complete weekly overview.</span>
            </div>

            <div className="form-group slots-group">
              <span className="field-label">Meal Slots per Day</span>
              <div className="slot-checkboxes" role="group" aria-label="Meal Slots">
                {AVAILABLE_SLOTS.map((slot) => {
                  const isChecked = selectedSlots.includes(slot.id);
                  return (
                    <label
                      key={slot.id}
                      className={`slot-checkbox-label ${isChecked ? 'slot-checked' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleSlot(slot.id)}
                        disabled={isGenerating}
                        data-testid={`slot-checkbox-${slot.id}`}
                      />
                      <span>{slot.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="form-row preferences-row">
            <div className="form-group">
              <label htmlFor="gen-calories" className="field-label">
                Target Daily Calories (Optional)
              </label>
              <input
                id="gen-calories"
                type="number"
                min={800}
                max={6000}
                placeholder="e.g. 2000 kcal"
                value={targetCalories}
                onChange={(e) => setTargetCalories(e.target.value)}
                className="input-field"
                disabled={isGenerating}
                data-testid="gen-calories-input"
              />
              <span className="field-hint">Can be derived from the Nutrition Biometrics Calculator.</span>
            </div>

            <div className="form-group">
              <label htmlFor="gen-diet" className="field-label">
                Dietary Preference
              </label>
              <select
                id="gen-diet"
                value={diet}
                onChange={(e) => setDiet(e.target.value)}
                className="select-field"
                disabled={isGenerating}
                data-testid="gen-diet-select"
              >
                {DIET_OPTIONS.map((d) => (
                  <option key={d.value} value={d.value}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="gen-cuisine" className="field-label">
                Cuisine Style
              </label>
              <select
                id="gen-cuisine"
                value={cuisine}
                onChange={(e) => setCuisine(e.target.value)}
                className="select-field"
                disabled={isGenerating}
                data-testid="gen-cuisine-select"
              >
                {CUISINE_OPTIONS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="gen-max-time" className="field-label">
                Max Prep Time (Minutes)
              </label>
              <input
                id="gen-max-time"
                type="number"
                min={5}
                max={300}
                placeholder="e.g. 45"
                value={maxTime}
                onChange={(e) => setMaxTime(e.target.value)}
                className="input-field"
                disabled={isGenerating}
                data-testid="gen-max-time-input"
              />
            </div>
          </div>

          <div className="form-actions">
            <button
              type="submit"
              className="btn btn-primary btn-generate"
              disabled={isGenerating}
              data-testid="submit-generate-plan-btn"
            >
              {isGenerating ? 'Synthesizing Meal Schedule...' : 'Generate Meal Plan Proposal'}
            </button>
            {onCancel && (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onCancel}
                disabled={isGenerating}
                data-testid="cancel-generate-btn"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      ) : (
        <div className="proposal-preview-section" data-testid="proposal-preview-section">
          <div className="proposal-warning-banner" role="status" data-testid="proposal-status-banner">
            <span className="editorial-badge warn-badge">Proposal Mode (Unsaved)</span>
            <p className="warn-text">
              This meal plan proposal has not yet been committed to your session. Review the schedule
              below and click <strong>&ldquo;Save Plan to Guest Session&rdquo;</strong> to persist it and unlock
              cooking execution progress and shopping list generation.
            </p>
          </div>

          {proposal.notes && proposal.notes.length > 0 && (
            <div className="proposal-notes" data-testid="proposal-notes">
              <span className="notes-label">Generation Notes:</span>
              <ul className="notes-list">
                {proposal.notes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="proposal-name-row">
            <label htmlFor="plan-name-input" className="field-label">
              Plan Title
            </label>
            <input
              id="plan-name-input"
              type="text"
              value={planName}
              onChange={(e) => setPlanName(e.target.value)}
              className="input-field plan-name-input"
              disabled={isSaving}
              data-testid="proposal-name-input"
            />
          </div>

          <div className="proposal-days-list" data-testid="proposal-days-list">
            {proposal.days.map((day) => (
              <div key={day.day_index} className="proposal-day-card" data-testid={`proposal-day-${day.day_index}`}>
                <div className="proposal-day-header">
                  <h4 className="day-title">Day {day.day_index + 1}</h4>
                  {day.day_total_calories_kcal !== null && day.day_total_calories_kcal !== undefined ? (
                    <span className="day-cal-badge" data-testid={`proposal-day-calories-${day.day_index}`}>
                      Est. {Math.round(day.day_total_calories_kcal)} kcal
                    </span>
                  ) : (
                    <span className="day-cal-badge uncalc-badge">Calories uncalculated</span>
                  )}
                </div>

                <div className="proposal-slots-grid">
                  {day.slots.map((slot, sIdx) => (
                    <div
                      key={sIdx}
                      className="proposal-slot-item"
                      data-testid={`proposal-slot-${day.day_index}-${slot.slot_type}`}
                    >
                      <span className="slot-type-badge">{slot.slot_type.toUpperCase()}</span>
                      <span className="slot-recipe-title">{slot.title}</span>
                      <div className="slot-meta">
                        {slot.total_time_minutes ? <span>⏱ {slot.total_time_minutes} min</span> : null}
                        {slot.estimated_calories_kcal ? (
                          <span>🔥 {Math.round(slot.estimated_calories_kcal)} kcal</span>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="proposal-actions">
            <button
              type="button"
              className="btn btn-primary btn-save-plan"
              onClick={handleConfirmSave}
              disabled={isSaving}
              data-testid="save-generated-plan-btn"
            >
              {isSaving ? 'Saving to Guest Session...' : 'Save Plan to Guest Session'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setProposal(null)}
              disabled={isSaving}
              data-testid="discard-proposal-btn"
            >
              Discard &amp; Reconfigure
            </button>
          </div>
        </div>
      )}

      <style>{`
        .generator-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          padding: var(--space-6);
        }

        .generator-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .generator-title {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
        }

        .generator-desc {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .generator-form {
          display: flex;
          flex-direction: column;
          gap: var(--space-5);
        }

        .form-row {
          display: grid;
          gap: var(--space-4);
        }

        .days-slots-row {
          grid-template-columns: 200px 1fr;
        }

        @media (max-width: 768px) {
          .days-slots-row {
            grid-template-columns: 1fr;
          }
        }

        .preferences-row {
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        }

        .form-group {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .field-label {
          font-size: var(--text-xs);
          font-weight: 600;
          letter-spacing: 0.05em;
          text-transform: uppercase;
        }

        .field-hint {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .input-field,
        .select-field {
          padding: 0.6rem 0.8rem;
          font-size: var(--text-sm);
          font-family: inherit;
          background-color: var(--color-bg);
          color: var(--color-text);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          outline: none;
        }

        .input-field:focus,
        .select-field:focus {
          border-color: var(--color-text);
        }

        .slot-checkboxes {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
        }

        .slot-checkbox-label {
          display: inline-flex;
          align-items: center;
          gap: 0.4rem;
          padding: 0.4rem 0.8rem;
          font-size: var(--text-sm);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          cursor: pointer;
          background: var(--color-surface);
          user-select: none;
        }

        .slot-checkbox-label.slot-checked {
          background-color: var(--color-text);
          color: var(--color-bg);
          border-color: var(--color-text);
        }

        .slot-checkbox-label input {
          margin: 0;
          border-radius: 0px;
        }

        .form-actions,
        .proposal-actions {
          display: flex;
          gap: var(--space-3);
          flex-wrap: wrap;
          margin-top: var(--space-2);
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

        .proposal-warning-banner {
          padding: var(--space-4);
          background-color: rgba(217, 119, 6, 0.08);
          border: 1px solid #d97706;
          border-radius: 0px !important;
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .warn-badge {
          background-color: #d97706;
          color: #ffffff;
          align-self: flex-start;
        }

        .warn-text {
          font-size: var(--text-sm);
          color: var(--color-text);
          margin: 0;
        }

        .proposal-preview-section {
          display: flex;
          flex-direction: column;
          gap: var(--space-5);
        }

        .proposal-notes {
          padding: var(--space-3) var(--space-4);
          background: var(--color-surface);
          border-left: 3px solid var(--color-text);
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .notes-list {
          margin: 0.3rem 0 0 var(--space-4);
          padding: 0;
        }

        .proposal-name-row {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          max-width: 450px;
        }

        .proposal-days-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .proposal-day-card {
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          background: var(--color-surface);
        }

        .proposal-day-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-2);
        }

        .day-title {
          font-family: var(--font-serif);
          font-size: var(--text-lg);
          margin: 0;
        }

        .day-cal-badge {
          font-size: var(--text-xs);
          font-weight: 600;
          padding: 0.2rem 0.5rem;
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
        }

        .uncalc-badge {
          color: var(--color-text-secondary);
        }

        .proposal-slots-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: var(--space-3);
        }

        .proposal-slot-item {
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          padding: var(--space-3);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          background: var(--color-bg);
        }

        .slot-type-badge {
          font-size: 10px;
          letter-spacing: 0.08em;
          font-weight: 700;
          color: var(--color-text-secondary);
        }

        .slot-recipe-title {
          font-size: var(--text-sm);
          font-weight: 600;
          line-height: 1.3;
        }

        .slot-meta {
          display: flex;
          gap: var(--space-3);
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }
      `}</style>
    </div>
  );
};
