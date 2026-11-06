import React from 'react';
import { RecipeSortOption } from '../../api/types/recipe';

interface RecipeSortControlProps {
  value: RecipeSortOption;
  onChange: (sort: RecipeSortOption) => void;
  disabled?: boolean;
}

const SORT_OPTIONS: Array<{ value: RecipeSortOption; label: string }> = [
  { value: 'relevance', label: 'Most Relevant' },
  { value: 'rating', label: 'Highest Rated' },
  { value: 'time_asc', label: 'Fastest Total Time' },
  { value: 'time_desc', label: 'Longest Total Time' },
];

export const RecipeSortControl: React.FC<RecipeSortControlProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  return (
    <div className="sort-control-wrapper">
      <label htmlFor="recipe-sort-select" className="sort-label">
        Sort By:
      </label>
      <select
        id="recipe-sort-select"
        className="sort-select"
        value={value}
        onChange={(e) => onChange(e.target.value as RecipeSortOption)}
        disabled={disabled}
        aria-label="Sort recipes by"
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <style>{`
        .sort-control-wrapper {
          display: inline-flex;
          align-items: center;
          gap: var(--space-2);
        }

        .sort-label {
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-secondary);
          white-space: nowrap;
        }

        .sort-select {
          padding: var(--space-2) var(--space-3);
          font-family: var(--font-sans);
          font-size: var(--text-sm);
          background-color: var(--color-surface);
          color: var(--color-text-primary);
          border: 1px solid var(--color-border);
          outline: none;
          cursor: pointer;
        }

        .sort-select:focus {
          border-color: var(--color-accent);
        }
      `}</style>
    </div>
  );
};

