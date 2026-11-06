import React, { useState } from 'react';
import { ActiveFilters } from '../../hooks/useRecipeSearch';
import { RecipeSourceDataset } from '../../api/types/recipe';

interface RecipeFiltersProps {
  filters: ActiveFilters;
  onSetFilter: <K extends keyof ActiveFilters>(key: K, value: ActiveFilters[K] | undefined) => void;
  onRemoveFilter: (key: keyof ActiveFilters) => void;
  onClearAll: () => void;
  disabled?: boolean;
}

// Conservative supported filter values strictly backed by verified database records
const CUISINE_OPTIONS = [
  'American',
  'Asian',
  'Italian',
  'Mexican',
  'Indian',
  'French',
  'Chinese',
  'Greek',
  'Mediterranean',
];

const DIET_OPTIONS = [
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'gluten-free', label: 'Gluten-Free' },
  { value: 'low-carb', label: 'Low-Carb' },
  { value: 'healthy', label: 'Healthy' },
  { value: 'dairy-free', label: 'Dairy-Free' },
];

const TIME_OPTIONS = [
  { value: 15, label: '≤ 15 mins (Quick)' },
  { value: 30, label: '≤ 30 mins' },
  { value: 45, label: '≤ 45 mins' },
  { value: 60, label: '≤ 60 mins (1 hr)' },
  { value: 90, label: '≤ 90 mins' },
  { value: 120, label: '≤ 2 hours' },
];

const DATASET_OPTIONS: Array<{ value: RecipeSourceDataset; label: string }> = [
  { value: 'food_com', label: 'Food.com (User Rated)' },
  { value: 'recipenlg', label: 'RecipeNLG (Procedural Text)' },
];

export const RecipeFilters: React.FC<RecipeFiltersProps> = ({
  filters,
  onSetFilter,
  onRemoveFilter,
  onClearAll,
  disabled = false,
}) => {
  const [mobileExpanded, setMobileExpanded] = useState<boolean>(false);

  // Check if any filters are active
  const hasActiveFilters = Boolean(
    filters.cuisine ||
      filters.diet ||
      filters.tag ||
      filters.max_time ||
      filters.source_dataset
  );

  return (
    <div className="recipe-filters-wrapper">
      {/* Mobile Toggle Button */}
      <div className="filters-mobile-toggle">
        <button
          type="button"
          className="btn btn-secondary mobile-filter-btn"
          onClick={() => setMobileExpanded((prev) => !prev)}
          aria-expanded={mobileExpanded}
          aria-controls="filters-panel"
        >
          <span>{mobileExpanded ? 'Hide Filters ▲' : 'Show Filters ▼'}</span>
          {hasActiveFilters && <span className="active-dot" aria-label="Filters active" />}
        </button>
      </div>

      {/* Main Filter Controls Panel */}
      <div
        id="filters-panel"
        className={`filters-panel ${mobileExpanded ? 'filters-panel-open' : ''}`}
      >
        <div className="filter-group">
          <label htmlFor="filter-cuisine" className="filter-label">
            Cuisine
          </label>
          <select
            id="filter-cuisine"
            className="filter-select"
            value={filters.cuisine || ''}
            onChange={(e) => onSetFilter('cuisine', e.target.value || undefined)}
            disabled={disabled}
          >
            <option value="">All Cuisines</option>
            {CUISINE_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-diet" className="filter-label">
            Dietary Category
          </label>
          <select
            id="filter-diet"
            className="filter-select"
            value={filters.diet || ''}
            onChange={(e) => onSetFilter('diet', e.target.value || undefined)}
            disabled={disabled}
          >
            <option value="">All Diets</option>
            {DIET_OPTIONS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-max-time" className="filter-label">
            Max Total Time
          </label>
          <select
            id="filter-max-time"
            className="filter-select"
            value={filters.max_time || ''}
            onChange={(e) =>
              onSetFilter('max_time', e.target.value ? parseInt(e.target.value, 10) : undefined)
            }
            disabled={disabled}
          >
            <option value="">Any Time</option>
            {TIME_OPTIONS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label htmlFor="filter-dataset" className="filter-label">
            Source Dataset
          </label>
          <select
            id="filter-dataset"
            className="filter-select"
            value={filters.source_dataset || ''}
            onChange={(e) =>
              onSetFilter(
                'source_dataset',
                (e.target.value as RecipeSourceDataset) || undefined
              )
            }
            disabled={disabled}
          >
            <option value="">All Datasets (50,000)</option>
            {DATASET_OPTIONS.map((ds) => (
              <option key={ds.value} value={ds.value}>
                {ds.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Active Filter Chips Bar */}
      {hasActiveFilters && (
        <div className="active-filters-bar" aria-label="Active filters">
          <span className="active-filters-label">Active Filters:</span>

          {filters.cuisine && (
            <button
              type="button"
              className="active-filter-chip"
              onClick={() => onRemoveFilter('cuisine')}
              aria-label={`Remove cuisine filter: ${filters.cuisine}`}
            >
              Cuisine: <strong>{filters.cuisine}</strong> &times;
            </button>
          )}

          {filters.diet && (
            <button
              type="button"
              className="active-filter-chip"
              onClick={() => onRemoveFilter('diet')}
              aria-label={`Remove diet filter: ${filters.diet}`}
            >
              Diet: <strong>{filters.diet}</strong> &times;
            </button>
          )}

          {filters.max_time && (
            <button
              type="button"
              className="active-filter-chip"
              onClick={() => onRemoveFilter('max_time')}
              aria-label={`Remove max time filter: ${filters.max_time} mins`}
            >
              Time: <strong>&le; {filters.max_time}m</strong> &times;
            </button>
          )}

          {filters.source_dataset && (
            <button
              type="button"
              className="active-filter-chip"
              onClick={() => onRemoveFilter('source_dataset')}
              aria-label={`Remove dataset filter: ${filters.source_dataset}`}
            >
              Dataset:{' '}
              <strong>
                {filters.source_dataset === 'food_com' ? 'Food.com' : 'RecipeNLG'}
              </strong>{' '}
              &times;
            </button>
          )}

          {filters.tag && (
            <button
              type="button"
              className="active-filter-chip"
              onClick={() => onRemoveFilter('tag')}
              aria-label={`Remove tag filter: ${filters.tag}`}
            >
              Tag: <strong>{filters.tag}</strong> &times;
            </button>
          )}

          <button
            type="button"
            className="clear-all-filters-btn"
            onClick={onClearAll}
            aria-label="Clear all active filters"
          >
            Clear All
          </button>
        </div>
      )}

      <style>{`
        .recipe-filters-wrapper {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-4);
        }

        .filters-mobile-toggle {
          display: none;
        }

        .mobile-filter-btn {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-2) var(--space-4);
        }

        .active-dot {
          width: 8px;
          height: 8px;
          background-color: var(--color-accent);
          display: inline-block;
        }

        .filters-panel {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: var(--space-4);
        }

        .filter-group {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .filter-label {
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
        }

        .filter-select {
          padding: var(--space-2) var(--space-3);
          font-family: var(--font-sans);
          font-size: var(--text-sm);
          background-color: var(--color-surface-subtle);
          color: var(--color-text-primary);
          border: 1px solid var(--color-border);
          outline: none;
          cursor: pointer;
        }

        .filter-select:focus {
          border-color: var(--color-accent);
        }

        .active-filters-bar {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: var(--space-2);
          border-top: 1px solid var(--color-border);
          padding-top: var(--space-3);
          margin-top: var(--space-1);
        }

        .active-filters-label {
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-muted);
        }

        .active-filter-chip {
          background-color: var(--color-tag-bg);
          color: var(--color-tag-text);
          border: 1px solid var(--color-border-strong);
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          padding: 0.2rem 0.5rem;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: var(--space-1);
          transition: background-color var(--transition-fast);
        }

        .active-filter-chip:hover {
          background-color: var(--color-surface-hover);
          color: var(--color-accent);
        }

        .clear-all-filters-btn {
          background: transparent;
          border: none;
          color: var(--color-accent);
          font-size: var(--text-xs);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          cursor: pointer;
          padding: 0.2rem 0.5rem;
          text-decoration: underline;
        }

        .clear-all-filters-btn:hover {
          color: var(--color-accent-hover);
        }

        @media (max-width: 768px) {
          .filters-mobile-toggle {
            display: block;
          }

          .filters-panel {
            display: none;
            grid-template-columns: 1fr;
          }

          .filters-panel-open {
            display: grid;
            margin-top: var(--space-3);
          }
        }
      `}</style>
    </div>
  );
};

