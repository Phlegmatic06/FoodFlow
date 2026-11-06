import React from 'react';
import { RecipeIngredientItem } from '../../api/types/recipe';

interface RecipeIngredientsProps {
  ingredients: RecipeIngredientItem[];
  checkedPositions: Set<number>;
  onToggleIngredient: (position: number) => void;
  onResetChecklist?: () => void;
}

export const RecipeIngredients: React.FC<RecipeIngredientsProps> = ({
  ingredients,
  checkedPositions,
  onToggleIngredient,
  onResetChecklist,
}) => {
  // Format numeric quantity cleanly if available
  const formatQuantity = (quantity?: number | null) => {
    if (quantity === null || quantity === undefined) return null;
    // Format float nicely (e.g. 1.5 -> 1.5, 2.0 -> 2)
    return Number.isInteger(quantity) ? quantity.toString() : quantity.toString();
  };

  const totalCount = ingredients.length;
  const checkedCount = checkedPositions.size;

  return (
    <section className="recipe-ingredients-section" data-testid="recipe-ingredients-section">
      <div className="section-header-row">
        <div>
          <h2 className="section-heading" data-testid="ingredients-heading">
            Ingredients
          </h2>
          <span className="ingredient-count-subtitle">
            {totalCount} {totalCount === 1 ? 'item' : 'items'} in recipe
          </span>
        </div>

        {totalCount > 0 && (
          <div className="checklist-controls" data-testid="checklist-controls">
            <span className="checklist-progress" data-testid="checklist-progress">
              {checkedCount} of {totalCount} prepped
            </span>
            {checkedCount > 0 && onResetChecklist && (
              <button
                type="button"
                className="btn btn-secondary btn-reset-checklist"
                onClick={onResetChecklist}
                data-testid="reset-checklist-btn"
              >
                Reset
              </button>
            )}
          </div>
        )}
      </div>

      {totalCount === 0 ? (
        <div className="editorial-card empty-ingredients" data-testid="empty-ingredients">
          <p>No ingredients listed for this recipe.</p>
        </div>
      ) : (
        <ul className="ingredients-list" data-testid="ingredients-list">
          {ingredients.map((item) => {
            const isChecked = checkedPositions.has(item.position);
            const formattedQty = formatQuantity(item.quantity);
            const hasMeasurement = formattedQty !== null || Boolean(item.unit);

            return (
              <li
                key={item.position}
                className={`ingredient-list-item ${isChecked ? 'item-checked' : ''}`}
                data-testid={`ingredient-item-${item.position}`}
              >
                <label className="ingredient-checkbox-label">
                  <input
                    type="checkbox"
                    className="ingredient-checkbox"
                    checked={isChecked}
                    onChange={() => onToggleIngredient(item.position)}
                    data-testid={`ingredient-checkbox-${item.position}`}
                    aria-label={`Mark ${item.raw_text} as collected`}
                  />
                  <div className="ingredient-text-container">
                    <span className="ingredient-raw-text">
                      {hasMeasurement && (
                        <strong className="ingredient-measurement">
                          {formattedQty ? `${formattedQty} ` : ''}
                          {item.unit ? `${item.unit} ` : ''}
                        </strong>
                      )}
                      {item.raw_text}
                    </span>

                    {item.canonical_name && (
                      <span
                        className="editorial-badge canonical-match-badge"
                        data-testid={`canonical-badge-${item.position}`}
                        title="Mapped to FoodFlow canonical taxonomy"
                      >
                        Canonical: {item.canonical_name}
                      </span>
                    )}
                  </div>
                </label>
              </li>
            );
          })}
        </ul>
      )}

      <style>{`
        .recipe-ingredients-section {
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

        .ingredient-count-subtitle {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .checklist-controls {
          display: flex;
          align-items: center;
          gap: var(--space-3);
        }

        .checklist-progress {
          font-size: var(--text-xs);
          font-weight: 600;
          color: var(--color-text-secondary);
          background-color: var(--color-surface-subtle);
          padding: var(--space-1) var(--space-2);
          border: 1px solid var(--color-border);
        }

        .btn-reset-checklist {
          padding: 0.2rem 0.5rem;
          font-size: var(--text-xs);
        }

        .empty-ingredients {
          padding: var(--space-4);
          color: var(--color-text-muted);
          font-style: italic;
        }

        .ingredients-list {
          list-style: none;
          display: flex;
          flex-direction: column;
          gap: 1px;
          background-color: var(--color-border);
          border: 1px solid var(--color-border);
        }

        .ingredient-list-item {
          background-color: var(--color-surface);
          padding: var(--space-3) var(--space-4);
          transition: background-color var(--transition-fast);
        }

        .ingredient-list-item:hover {
          background-color: var(--color-surface-subtle);
        }

        .ingredient-list-item.item-checked {
          background-color: var(--color-bg);
          opacity: 0.7;
        }

        .ingredient-checkbox-label {
          display: flex;
          align-items: flex-start;
          gap: var(--space-3);
          cursor: pointer;
          user-select: none;
          width: 100%;
        }

        .ingredient-checkbox {
          margin-top: 0.25rem;
          width: 1.1rem;
          height: 1.1rem;
          accent-color: var(--color-accent);
          cursor: pointer;
        }

        .ingredient-text-container {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          flex: 1;
        }

        .ingredient-raw-text {
          font-size: var(--text-base);
          color: var(--color-text-primary);
          line-height: 1.4;
        }

        .item-checked .ingredient-raw-text {
          text-decoration: line-through;
          color: var(--color-text-muted);
        }

        .ingredient-measurement {
          color: var(--color-accent);
          font-weight: 600;
        }

        .item-checked .ingredient-measurement {
          color: var(--color-text-muted);
        }

        .canonical-match-badge {
          align-self: flex-start;
          font-size: 0.65rem;
          background-color: var(--color-secondary-subtle);
          color: var(--color-secondary-accent);
          border-color: var(--color-secondary-accent);
        }
      `}</style>
    </section>
  );
};

