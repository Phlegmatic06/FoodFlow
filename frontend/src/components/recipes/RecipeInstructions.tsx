import React from 'react';
import { RecipeInstructionItem } from '../../api/types/recipe';

interface RecipeInstructionsProps {
  instructions: RecipeInstructionItem[];
  onEnterCookingMode?: () => void;
  activeStepNumber?: number;
}

export const RecipeInstructions: React.FC<RecipeInstructionsProps> = ({
  instructions,
  onEnterCookingMode,
  activeStepNumber,
}) => {
  const totalSteps = instructions.length;

  return (
    <section className="recipe-instructions-section" data-testid="recipe-instructions-section">
      <div className="section-header-row">
        <div>
          <h2 className="section-heading" data-testid="instructions-heading">
            Preparation Instructions
          </h2>
          <span className="instruction-count-subtitle">
            {totalSteps} {totalSteps === 1 ? 'step' : 'steps'} in sequence
          </span>
        </div>

        {totalSteps > 0 && onEnterCookingMode && (
          <button
            type="button"
            className="btn btn-primary btn-enter-cooking"
            onClick={onEnterCookingMode}
            data-testid="instructions-enter-cooking-btn"
          >
            Start Cooking Mode &rarr;
          </button>
        )}
      </div>

      {totalSteps === 0 ? (
        <div className="editorial-card empty-instructions" data-testid="empty-instructions">
          <p className="empty-instructions-message">
            No cooking instructions available for this recipe.
          </p>
        </div>
      ) : (
        <ol className="instructions-list" data-testid="instructions-list">
          {instructions.map((step) => {
            const isActive = activeStepNumber === step.step_number;

            return (
              <li
                key={step.step_number}
                className={`instruction-step-card ${isActive ? 'step-active' : ''}`}
                data-testid={`instruction-step-${step.step_number}`}
              >
                <div className="step-header">
                  <span className="step-number-badge">Step {step.step_number}</span>
                </div>
                <div className="step-body">
                  <p className="step-instruction-text">{step.instruction}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <style>{`
        .recipe-instructions-section {
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

        .instruction-count-subtitle {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .btn-enter-cooking {
          font-size: var(--text-xs);
        }

        .empty-instructions {
          padding: var(--space-4);
          color: var(--color-text-muted);
          font-style: italic;
        }

        .instructions-list {
          list-style: none;
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .instruction-step-card {
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-5);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          transition: border-color var(--transition-fast);
        }

        .instruction-step-card:hover {
          border-color: var(--color-border-strong);
        }

        .instruction-step-card.step-active {
          border-left: 4px solid var(--color-accent);
          background-color: var(--color-surface-subtle);
        }

        .step-header {
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }

        .step-number-badge {
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-accent);
          background-color: var(--color-accent-subtle);
          padding: 0.15rem 0.5rem;
          border: 1px solid var(--color-accent);
        }

        .step-body {
          padding-top: var(--space-1);
        }

        .step-instruction-text {
          font-size: var(--text-base);
          line-height: 1.65;
          color: var(--color-text-primary);
        }
      `}</style>
    </section>
  );
};

