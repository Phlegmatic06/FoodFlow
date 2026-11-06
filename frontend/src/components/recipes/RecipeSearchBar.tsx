import React from 'react';

interface RecipeSearchBarProps {
  value: string;
  onChange: (val: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  loading?: boolean;
}

export const RecipeSearchBar: React.FC<RecipeSearchBarProps> = ({
  value,
  onChange,
  onSubmit,
  onClear,
  loading = false,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="search-bar-wrapper">
      <form
        className="search-bar-form"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <div className="search-input-container">
          <input
            type="search"
            className="search-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search recipes by title, ingredients, or culinary technique..."
            aria-label="Search recipes"
          />

          {value && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={onClear}
              aria-label="Clear search query"
              title="Clear search"
            >
              &times;
            </button>
          )}
        </div>

        <button
          type="submit"
          className="btn btn-primary search-submit-btn"
          aria-label="Submit recipe search"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      <style>{`
        .search-bar-wrapper {
          width: 100%;
        }

        .search-bar-form {
          display: flex;
          gap: var(--space-2);
          width: 100%;
        }

        .search-input-container {
          position: relative;
          flex: 1;
          display: flex;
          align-items: center;
        }

        .search-input {
          width: 100%;
          padding: var(--space-3) var(--space-4);
          font-family: var(--font-sans);
          font-size: var(--text-base);
          background-color: var(--color-surface);
          color: var(--color-text-primary);
          border: 1px solid var(--color-border);
          outline: none;
          transition: border-color var(--transition-fast);
        }

        .search-input:focus {
          border-color: var(--color-accent);
          outline: 1px solid var(--color-accent);
        }

        .search-input::placeholder {
          color: var(--color-text-muted);
          font-style: italic;
        }

        .clear-search-btn {
          position: absolute;
          right: var(--space-3);
          background: transparent;
          border: none;
          color: var(--color-text-muted);
          font-size: var(--text-xl);
          line-height: 1;
          cursor: pointer;
          padding: var(--space-1);
        }

        .clear-search-btn:hover {
          color: var(--color-text-primary);
        }

        .search-submit-btn {
          white-space: nowrap;
          padding-left: var(--space-6);
          padding-right: var(--space-6);
        }

        @media (max-width: 600px) {
          .search-bar-form {
            flex-direction: column;
          }

          .search-submit-btn {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
};
