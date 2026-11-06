import React, { useEffect, useState, useCallback } from 'react';
import { RecipeIngredientItem, RecipeInstructionItem } from '../../api/types/recipe';

interface CookingModeProps {
  recipeTitle: string;
  instructions: RecipeInstructionItem[];
  ingredients: RecipeIngredientItem[];
  currentStepIndex: number;
  onStepChange: (newIndex: number) => void;
  onExit: () => void;
  checkedIngredients: Set<number>;
  onToggleIngredient: (position: number) => void;
}

export const CookingMode: React.FC<CookingModeProps> = ({
  recipeTitle,
  instructions,
  ingredients,
  currentStepIndex,
  onStepChange,
  onExit,
  checkedIngredients,
  onToggleIngredient,
}) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const totalSteps = instructions.length;
  // Ensure step index stays in bounds
  const safeIndex = Math.max(0, Math.min(currentStepIndex, totalSteps - 1));
  const currentStep = instructions[safeIndex];

  const hasPrevious = safeIndex > 0;
  const hasNext = safeIndex < totalSteps - 1;

  const handlePrevious = useCallback(() => {
    if (hasPrevious) {
      onStepChange(safeIndex - 1);
    }
  }, [hasPrevious, onStepChange, safeIndex]);

  const handleNext = useCallback(() => {
    if (hasNext) {
      onStepChange(safeIndex + 1);
    }
  }, [hasNext, onStepChange, safeIndex]);

  // Keyboard navigation support: Left/Right arrows, p/n, and Escape to exit
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }

      if (e.key === 'ArrowRight' || e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        handleNext();
      } else if (e.key === 'ArrowLeft' || e.key === 'p' || e.key === 'P') {
        e.preventDefault();
        handlePrevious();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        onExit();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleNext, handlePrevious, onExit]);

  const progressPercentage =
    totalSteps > 0 ? Math.round(((safeIndex + 1) / totalSteps) * 100) : 0;

  return (
    <div className="cooking-mode-overlay" data-testid="cooking-mode">
      {/* Top Utility Header */}
      <header className="cooking-mode-header">
        <div className="header-meta-group">
          <span className="editorial-badge cooking-badge">Cooking Mode</span>
          <h2 className="cooking-recipe-title" title={recipeTitle}>
            {recipeTitle}
          </h2>
        </div>

        <div className="header-controls-group">
          <button
            type="button"
            className="btn btn-secondary btn-ingredients-toggle"
            onClick={() => setIsDrawerOpen((prev) => !prev)}
            aria-expanded={isDrawerOpen}
            aria-controls="cooking-ingredients-drawer"
            data-testid="toggle-ingredients-drawer-btn"
          >
            📋 Ingredients ({checkedIngredients.size}/{ingredients.length})
          </button>

          <button
            type="button"
            className="btn btn-primary btn-exit-cooking"
            onClick={onExit}
            data-testid="exit-cooking-mode-btn"
          >
            &times; Exit Cooking Mode
          </button>
        </div>
      </header>

      {/* Progress Bar Strip */}
      <div
        className="cooking-progress-strip"
        role="progressbar"
        aria-valuenow={safeIndex + 1}
        aria-valuemin={1}
        aria-valuemax={totalSteps}
        aria-label={`Cooking step progress: step ${safeIndex + 1} of ${totalSteps}`}
        data-testid="cooking-progress-bar"
      >
        <div
          className="progress-fill"
          style={{ width: `${progressPercentage}%` }}
          data-testid="cooking-progress-fill"
        />
      </div>

      {/* Main Focus Area */}
      <div className="cooking-main-layout">
        <main className="cooking-stage">
          <div className="step-counter-banner" data-testid="step-counter">
            <span className="current-step-label">
              Step {safeIndex + 1} of {totalSteps}
            </span>
            <span className="step-progress-percentage">{progressPercentage}% Complete</span>
          </div>

          <article className="editorial-card current-instruction-card" data-testid="current-instruction-card">
            <div className="instruction-step-badge">
              <span>Step {currentStep ? currentStep.step_number : safeIndex + 1}</span>
            </div>

            <p className="active-instruction-text" data-testid="active-instruction-text">
              {currentStep ? currentStep.instruction : 'No instructions found for this step.'}
            </p>
          </article>

          {/* Cooking Navigation Controls */}
          <nav className="cooking-nav-controls" aria-label="Step navigation">
            <button
              type="button"
              className="btn btn-secondary nav-btn prev-btn"
              onClick={handlePrevious}
              disabled={!hasPrevious}
              data-testid="cooking-prev-btn"
              aria-label="Previous step"
            >
              &larr; Previous Step
            </button>

            <span className="step-indicator-text" data-testid="step-indicator-text">
              {safeIndex + 1} / {totalSteps}
            </span>

            <button
              type="button"
              className="btn btn-primary nav-btn next-btn"
              onClick={handleNext}
              disabled={!hasNext}
              data-testid="cooking-next-btn"
              aria-label="Next step"
            >
              Next Step &rarr;
            </button>
          </nav>

          <footer className="keyboard-hints" aria-hidden="true">
            <span>Shortcut: &larr; (P) Previous &bull; &rarr; (N) Next &bull; Esc Exit</span>
          </footer>
        </main>

        {/* Collapsible Ingredients Drawer / Sidebar */}
        <aside
          id="cooking-ingredients-drawer"
          className={`cooking-ingredients-panel ${isDrawerOpen ? 'drawer-open' : 'drawer-closed'}`}
          data-testid="cooking-ingredients-drawer"
          aria-label="Ingredients checklist"
        >
          <div className="drawer-header">
            <h3 className="drawer-title">Ingredients Checklist</h3>
            <span className="drawer-count">
              {checkedIngredients.size} of {ingredients.length} prepped
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-close-drawer"
              onClick={() => setIsDrawerOpen(false)}
              aria-label="Close ingredients checklist"
              data-testid="close-drawer-btn"
            >
              &times;
            </button>
          </div>

          <ul className="drawer-ingredients-list" data-testid="drawer-ingredients-list">
            {ingredients.map((ing) => {
              const isChecked = checkedIngredients.has(ing.position);
              return (
                <li
                  key={ing.position}
                  className={`drawer-ingredient-item ${isChecked ? 'item-checked' : ''}`}
                  data-testid={`drawer-ingredient-${ing.position}`}
                >
                  <label className="drawer-ingredient-label">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => onToggleIngredient(ing.position)}
                      data-testid={`drawer-checkbox-${ing.position}`}
                    />
                    <span className="drawer-ingredient-text">{ing.raw_text}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        </aside>
      </div>

      <style>{`
        .cooking-mode-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          z-index: 1000;
          background-color: var(--color-bg);
          color: var(--color-text-primary);
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }

        .cooking-mode-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--space-4) var(--space-6);
          background-color: var(--color-surface);
          border-bottom: 1px solid var(--color-border);
          gap: var(--space-4);
          flex-wrap: wrap;
        }

        .header-meta-group {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          flex: 1;
          min-width: 250px;
        }

        .cooking-badge {
          background-color: var(--color-accent);
          color: var(--color-accent-text);
          border: none;
        }

        .cooking-recipe-title {
          font-family: var(--font-serif);
          font-size: var(--text-lg);
          font-weight: 700;
          color: var(--color-text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .header-controls-group {
          display: flex;
          gap: var(--space-2);
          align-items: center;
        }

        .btn-ingredients-toggle, .btn-exit-cooking {
          font-size: var(--text-xs);
          padding: var(--space-2) var(--space-4);
        }

        .cooking-progress-strip {
          height: 6px;
          background-color: var(--color-border);
          width: 100%;
        }

        .progress-fill {
          height: 100%;
          background-color: var(--color-accent);
          transition: width var(--transition-normal);
        }

        .cooking-main-layout {
          display: flex;
          flex: 1;
          overflow: hidden;
          position: relative;
        }

        .cooking-stage {
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          padding: var(--space-6);
          overflow-y: auto;
          max-width: 900px;
          margin: 0 auto;
          width: 100%;
          gap: var(--space-6);
        }

        .step-counter-banner {
          display: flex;
          justify-content: space-between;
          width: 100%;
          font-size: var(--text-sm);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-muted);
          font-weight: 600;
        }

        .current-instruction-card {
          width: 100%;
          padding: var(--space-8);
          background-color: var(--color-surface);
          border: 2px solid var(--color-border-strong);
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          min-height: 250px;
          justify-content: center;
        }

        .instruction-step-badge {
          display: inline-block;
          align-self: flex-start;
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--color-accent);
          background-color: var(--color-accent-subtle);
          padding: 0.2rem 0.6rem;
          border: 1px solid var(--color-accent);
        }

        .active-instruction-text {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          line-height: 1.6;
          color: var(--color-text-primary);
          font-weight: 400;
        }

        @media (min-width: 768px) {
          .active-instruction-text {
            font-size: var(--text-3xl);
          }
        }

        .cooking-nav-controls {
          display: flex;
          justify-content: space-between;
          align-items: center;
          width: 100%;
          gap: var(--space-4);
        }

        .nav-btn {
          min-width: 160px;
          padding: var(--space-4) var(--space-6);
          font-size: var(--text-base);
        }

        .nav-btn:disabled {
          opacity: 0.35;
          cursor: not-allowed;
        }

        .step-indicator-text {
          font-family: var(--font-mono);
          font-size: var(--text-sm);
          font-weight: 600;
          color: var(--color-text-muted);
        }

        .keyboard-hints {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          letter-spacing: 0.04em;
        }

        .cooking-ingredients-panel {
          width: 320px;
          background-color: var(--color-surface);
          border-left: 1px solid var(--color-border);
          display: flex;
          flex-direction: column;
          transition: transform var(--transition-normal);
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          z-index: 10;
        }

        .cooking-ingredients-panel.drawer-closed {
          transform: translateX(100%);
        }

        .cooking-ingredients-panel.drawer-open {
          transform: translateX(0);
          box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
        }

        @media (min-width: 1100px) {
          .cooking-ingredients-panel {
            position: static;
            transform: none !important;
            box-shadow: none !important;
          }
          .btn-ingredients-toggle {
            display: none;
          }
          .btn-close-drawer {
            display: none;
          }
        }

        .drawer-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-4);
          border-bottom: 1px solid var(--color-border);
          gap: var(--space-2);
        }

        .drawer-title {
          font-size: var(--text-base);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .drawer-count {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
        }

        .btn-close-drawer {
          font-size: var(--text-lg);
          padding: 0 0.5rem;
          line-height: 1;
        }

        .drawer-ingredients-list {
          list-style: none;
          overflow-y: auto;
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 1px;
          background-color: var(--color-border);
        }

        .drawer-ingredient-item {
          background-color: var(--color-surface);
          padding: var(--space-3) var(--space-4);
        }

        .drawer-ingredient-item.item-checked {
          background-color: var(--color-bg);
          opacity: 0.6;
        }

        .drawer-ingredient-label {
          display: flex;
          align-items: flex-start;
          gap: var(--space-2);
          cursor: pointer;
        }

        .drawer-ingredient-label input {
          margin-top: 0.2rem;
          accent-color: var(--color-accent);
        }

        .drawer-ingredient-text {
          font-size: var(--text-sm);
          color: var(--color-text-primary);
        }

        .item-checked .drawer-ingredient-text {
          text-decoration: line-through;
          color: var(--color-text-muted);
        }
      `}</style>
    </div>
  );
};

