import React, { useState, useEffect, useRef, useCallback } from 'react';
import { recipeClient } from '../../api/recipeClient';
import { IngredientSuggestion } from '../../api/types/recipe';
import { UpdatePantryItemInput } from '../../api/types/planner';

interface PantryAddIngredientProps {
  onAddIngredient: (item: UpdatePantryItemInput) => Promise<void>;
  isSubmitting: boolean;
  existingCanonicalIds: Set<number>;
}

export const PantryAddIngredient: React.FC<PantryAddIngredientProps> = ({
  onAddIngredient,
  isSubmitting,
  existingCanonicalIds,
}) => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [suggestions, setSuggestions] = useState<IngredientSuggestion[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState<boolean>(false);
  const [suggestionError, setSuggestionError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState<boolean>(false);

  // Selected canonical ingredient
  const [selectedIngredient, setSelectedIngredient] = useState<IngredientSuggestion | null>(null);
  const [quantity, setQuantity] = useState<string>('');
  const [unit, setUnit] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch autocomplete suggestions with debouncing and request cancellation
  const fetchSuggestions = useCallback(async (query: string) => {
    const cleanQuery = query.trim();
    if (!cleanQuery) {
      setSuggestions([]);
      setIsLoadingSuggestions(false);
      setSuggestionError(null);
      setHasSearched(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoadingSuggestions(true);
    setSuggestionError(null);
    setHasSearched(true);

    try {
      const results = await recipeClient.getIngredientSuggestions(cleanQuery, 10, {
        signal: controller.signal,
      });
      setSuggestions(results);
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setSuggestionError(
        err instanceof Error ? err.message : 'Failed to query ingredient taxonomy suggestions'
      );
      setSuggestions([]);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoadingSuggestions(false);
      }
    }
  }, []);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchTerm(val);
    setSelectedIngredient(null);
    setFormError(null);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (!val.trim()) {
      setSuggestions([]);
      setHasSearched(false);
      return;
    }

    debounceTimerRef.current = setTimeout(() => {
      fetchSuggestions(val);
    }, 250);
  };

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSelectSuggestion = (suggestion: IngredientSuggestion) => {
    setSelectedIngredient(suggestion);
    setSearchTerm(suggestion.name);
    setSuggestions([]);
    setFormError(null);
  };

  const handleClearSelection = () => {
    setSelectedIngredient(null);
    setSearchTerm('');
    setQuantity('');
    setUnit('');
    setSuggestions([]);
    setFormError(null);
    setHasSearched(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!selectedIngredient) {
      setFormError('Please select a verified canonical ingredient from the taxonomy suggestions.');
      return;
    }

    if (existingCanonicalIds.has(selectedIngredient.id)) {
      setFormError(`'${selectedIngredient.name}' is already in your pantry inventory.`);
      return;
    }

    // Format raw_name: include quantity and unit if provided
    let rawText = selectedIngredient.name;
    const cleanQty = quantity.trim();
    const cleanUnit = unit.trim();

    if (cleanQty && cleanUnit) {
      rawText = `${cleanQty} ${cleanUnit} ${selectedIngredient.name}`;
    } else if (cleanQty) {
      rawText = `${cleanQty} ${selectedIngredient.name}`;
    }

    try {
      await onAddIngredient({
        raw_name: rawText,
        canonical_ingredient_id: selectedIngredient.id,
      });

      // Reset form after successful submission
      handleClearSelection();
    } catch (err: unknown) {
      setFormError(
        err instanceof Error ? err.message : 'Failed to add ingredient to pantry inventory.'
      );
    }
  };

  return (
    <div className="editorial-card add-ingredient-card" data-testid="pantry-add-ingredient-card">
      <div className="card-header-strip">
        <span className="editorial-badge">Taxonomy Linked</span>
        <h2 className="card-title">Add Ingredient to Pantry</h2>
      </div>

      <p className="add-lead-text">
        Search our 106-canonical ingredient taxonomy. Only verified ingredients can be accurately
        reconciled against recipes for overlap matching.
      </p>

      <form onSubmit={handleSubmit} className="add-ingredient-form" data-testid="add-ingredient-form" noValidate>
        {/* Ingredient Autocomplete Input */}
        <div className="form-group search-group">
          <label htmlFor="pantry-ingredient-search" className="form-label">
            Ingredient Name <span className="required-star">*</span>
          </label>
          <div className="search-input-wrap">
            <input
              id="pantry-ingredient-search"
              type="text"
              className="form-input"
              placeholder="Type to search (e.g. chicken breast, garlic, olive oil)..."
              value={searchTerm}
              onChange={handleSearchChange}
              autoComplete="off"
              data-testid="ingredient-search-input"
              aria-autocomplete="list"
              aria-expanded={suggestions.length > 0}
            />
            {selectedIngredient && (
              <button
                type="button"
                className="btn-clear-selection"
                onClick={handleClearSelection}
                data-testid="clear-selection-btn"
                title="Clear selected ingredient"
              >
                &times;
              </button>
            )}
          </div>

          {/* Selected Ingredient Confirmation Chip */}
          {selectedIngredient && (
            <div className="selected-confirmation-pill" data-testid="selected-ingredient-pill">
              <span className="pill-canonical-id">Canonical #{selectedIngredient.id}</span>
              <span className="pill-name">{selectedIngredient.name}</span>
              {selectedIngredient.category && (
                <span className="pill-category">({selectedIngredient.category})</span>
              )}
              {selectedIngredient.is_pantry_staple && (
                <span className="pill-staple">Staple</span>
              )}
            </div>
          )}

          {/* Suggestions Dropdown */}
          {isLoadingSuggestions && (
            <div className="suggestions-status" data-testid="suggestions-loading">
              <span>Searching canonical ingredient taxonomy...</span>
            </div>
          )}

          {suggestionError && (
            <div className="suggestions-error" role="alert" data-testid="suggestions-error">
              <span>{suggestionError}</span>
            </div>
          )}

          {!isLoadingSuggestions && hasSearched && !selectedIngredient && suggestions.length === 0 && (
            <div className="suggestions-empty" data-testid="suggestions-empty">
              <p>
                No canonical ingredient matching &ldquo;{searchTerm.trim()}&rdquo; was found in the taxonomy.
              </p>
              <span className="taxonomy-hint">
                FoodFlow uses a curated 106-canonical ingredient vocabulary to preserve culinary fidelity.
              </span>
            </div>
          )}

          {!isLoadingSuggestions && suggestions.length > 0 && !selectedIngredient && (
            <ul className="suggestions-dropdown" data-testid="suggestions-dropdown" role="listbox">
              {suggestions.map((item) => (
                <li
                  key={item.id}
                  className="suggestion-item"
                  onClick={() => handleSelectSuggestion(item)}
                  data-testid={`suggestion-item-${item.id}`}
                  role="option"
                  aria-selected="false"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      handleSelectSuggestion(item);
                    }
                  }}
                >
                  <div className="suggestion-info">
                    <span className="suggestion-name">{item.name}</span>
                    <span className="suggestion-id">ID: #{item.id}</span>
                  </div>
                  <div className="suggestion-meta">
                    {item.category && <span className="cat-pill">{item.category}</span>}
                    {item.is_pantry_staple && <span className="staple-pill">Staple</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Optional Quantity and Unit Inputs */}
        <div className="form-row two-col">
          <div className="form-group">
            <label htmlFor="pantry-ingredient-quantity" className="form-label">
              Quantity <span className="optional-tag">(Optional)</span>
            </label>
            <input
              id="pantry-ingredient-quantity"
              type="text"
              className="form-input"
              placeholder="e.g. 2, 0.5, 500"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              data-testid="ingredient-quantity-input"
            />
          </div>

          <div className="form-group">
            <label htmlFor="pantry-ingredient-unit" className="form-label">
              Unit of Measure <span className="optional-tag">(Optional)</span>
            </label>
            <input
              id="pantry-ingredient-unit"
              type="text"
              className="form-input"
              placeholder="e.g. cups, tbsp, lbs, cloves, g"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              data-testid="ingredient-unit-input"
            />
          </div>
        </div>

        {formError && (
          <div className="error-alert" role="alert" data-testid="add-ingredient-error">
            <span>{formError}</span>
          </div>
        )}

        <div className="form-actions-row">
          <button
            type="submit"
            className="btn btn-primary add-submit-btn"
            disabled={isSubmitting || !selectedIngredient}
            data-testid="add-ingredient-btn"
          >
            {isSubmitting ? 'Saving to Inventory...' : '+ Add to Inventory'}
          </button>
        </div>
      </form>

      <style>{`
        .add-ingredient-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-6);
        }

        .card-header-strip {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-3);
        }

        .card-title {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .add-lead-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          line-height: 1.5;
        }

        .add-ingredient-form {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .search-group {
          position: relative;
        }

        .search-input-wrap {
          position: relative;
          display: flex;
          align-items: center;
        }

        .btn-clear-selection {
          position: absolute;
          right: var(--space-3);
          background: none;
          border: none;
          font-size: var(--text-lg);
          cursor: pointer;
          color: var(--color-text-muted);
          padding: 0 var(--space-1);
        }

        .btn-clear-selection:hover {
          color: var(--color-text-primary);
        }

        .selected-confirmation-pill {
          margin-top: var(--space-2);
          display: inline-flex;
          align-items: center;
          gap: var(--space-2);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border-strong);
          padding: var(--space-1) var(--space-3);
          font-size: var(--text-xs);
        }

        .pill-canonical-id {
          font-family: var(--font-mono);
          font-weight: 700;
          color: var(--color-accent);
        }

        .pill-name {
          font-weight: 600;
          color: var(--color-text-primary);
        }

        .pill-category, .pill-staple {
          color: var(--color-text-muted);
        }

        .pill-staple {
          font-style: italic;
        }

        .suggestions-dropdown {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          z-index: 50;
          background-color: var(--color-surface);
          border: 1px solid var(--color-border-strong);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
          list-style: none;
          margin: 0;
          padding: 0;
          max-height: 240px;
          overflow-y: auto;
        }

        .suggestion-item {
          padding: var(--space-3) var(--space-4);
          border-bottom: 1px solid var(--color-border);
          display: flex;
          justify-content: space-between;
          align-items: center;
          cursor: pointer;
          transition: background-color 0.15s ease;
        }

        .suggestion-item:last-child {
          border-bottom: none;
        }

        .suggestion-item:hover, .suggestion-item:focus {
          background-color: var(--color-surface-subtle);
          outline: none;
        }

        .suggestion-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .suggestion-name {
          font-size: var(--text-sm);
          font-weight: 600;
          color: var(--color-text-primary);
        }

        .suggestion-id {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-family: var(--font-mono);
        }

        .suggestion-meta {
          display: flex;
          gap: var(--space-2);
        }

        .cat-pill, .staple-pill {
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          padding: 2px 6px;
          border: 1px solid var(--color-border);
          background-color: var(--color-surface-subtle);
          color: var(--color-text-secondary);
        }

        .staple-pill {
          border-color: var(--color-accent);
          color: var(--color-accent);
        }

        .suggestions-status, .suggestions-empty, .suggestions-error {
          padding: var(--space-3);
          font-size: var(--text-xs);
          margin-top: var(--space-2);
          border: 1px solid var(--color-border);
          background-color: var(--color-surface-subtle);
        }

        .suggestions-empty p {
          font-weight: 600;
          color: var(--color-text-primary);
          margin-bottom: var(--space-1);
        }

        .taxonomy-hint {
          color: var(--color-text-muted);
          line-height: 1.4;
        }

        .suggestions-error {
          border-color: var(--color-error);
          color: var(--color-error);
        }

        .optional-tag {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-weight: normal;
        }

        .required-star {
          color: var(--color-error);
        }

        .error-alert {
          background-color: var(--color-error-subtle);
          border: 1px solid var(--color-error);
          color: var(--color-error);
          padding: var(--space-3);
          font-size: var(--text-xs);
          font-weight: 600;
        }

        .form-actions-row {
          display: flex;
          justify-content: flex-end;
          margin-top: var(--space-2);
        }

        .add-submit-btn {
          font-weight: 600;
        }
      `}</style>
    </div>
  );
};

