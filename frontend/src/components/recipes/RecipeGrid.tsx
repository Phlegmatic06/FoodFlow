import React from 'react';
import { RecipeSummary } from '../../api/types/recipe';
import { ApiError } from '../../api/types/common';
import { RecipeCard } from './RecipeCard';

interface RecipeGridProps {
  recipes: RecipeSummary[];
  loading: boolean;
  error: ApiError | null;
  onRetry: () => void;
  onClearFilters?: () => void;
  hasActiveFilters?: boolean;
}

export const RecipeGrid: React.FC<RecipeGridProps> = ({
  recipes,
  loading,
  error,
  onRetry,
  onClearFilters,
  hasActiveFilters = false,
}) => {
  // 1. Loading State
  if (loading) {
    return (
      <div className="recipe-grid-loading" aria-busy="true" aria-label="Loading recipes">
        <div className="loading-indicator">
          <span className="editorial-badge">Searching Catalogue</span>
          <p className="loading-text">Querying 50,000 recipes across PostgreSQL...</p>
        </div>
        <div className="grid-skeleton-container" aria-hidden="true">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="editorial-card skeleton-card">
              <div className="skeleton-header" />
              <div className="skeleton-body">
                <div className="skeleton-line skeleton-title" />
                <div className="skeleton-line skeleton-meta" />
                <div className="skeleton-line skeleton-desc" />
              </div>
            </div>
          ))}
        </div>
        <style>{`
          .recipe-grid-loading {
            display: flex;
            flex-direction: column;
            gap: var(--space-6);
            padding: var(--space-4) 0;
          }

          .loading-indicator {
            display: flex;
            align-items: center;
            gap: var(--space-3);
          }

          .loading-text {
            font-size: var(--text-sm);
            color: var(--color-text-secondary);
            font-style: italic;
          }

          .grid-skeleton-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: var(--space-6);
          }

          .skeleton-card {
            height: 240px;
            padding: 0;
            background-color: var(--color-surface);
            border: 1px solid var(--color-border);
            display: flex;
            flex-direction: column;
          }

          .skeleton-header {
            height: 70px;
            background-color: var(--color-surface-subtle);
            border-bottom: 1px solid var(--color-border);
          }

          .skeleton-body {
            padding: var(--space-4);
            display: flex;
            flex-direction: column;
            gap: var(--space-3);
          }

          .skeleton-line {
            background-color: var(--color-surface-subtle);
            height: 14px;
          }

          .skeleton-title {
            width: 80%;
            height: 18px;
          }

          .skeleton-meta {
            width: 50%;
          }

          .skeleton-desc {
            width: 90%;
          }
        `}</style>
      </div>
    );
  }

  // 2. Error State
  if (error) {
    return (
      <div className="editorial-card recipe-grid-error" role="alert">
        <span className="editorial-badge" style={{ backgroundColor: 'var(--color-error-subtle)', color: 'var(--color-error)' }}>
          API Error
        </span>
        <h3 className="error-heading">Failed to load recipes</h3>
        <p className="error-message">{error.message}</p>
        {error.requestId && (
          <p className="error-request-id">
            Request ID: <code>{error.requestId}</code>
          </p>
        )}
        <div className="error-actions">
          <button type="button" className="btn btn-primary" onClick={onRetry}>
            Try Again
          </button>
        </div>

        <style>{`
          .recipe-grid-error {
            border-left: 4px solid var(--color-error);
            padding: var(--space-6);
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: var(--space-2);
          }

          .error-heading {
            font-size: var(--text-lg);
            font-family: var(--font-serif);
            color: var(--color-text-primary);
            margin-top: var(--space-2);
          }

          .error-message {
            font-size: var(--text-sm);
            color: var(--color-text-secondary);
          }

          .error-request-id {
            font-size: var(--text-xs);
            color: var(--color-text-muted);
            font-family: var(--font-mono);
          }

          .error-actions {
            margin-top: var(--space-3);
          }
        `}</style>
      </div>
    );
  }

  // 3. Empty State
  if (recipes.length === 0) {
    return (
      <div className="editorial-card recipe-grid-empty" role="status">
        <span className="editorial-badge">Zero Results</span>
        <h3 className="empty-heading">No matching recipes found</h3>
        <p className="empty-message">
          We could not find any recipes matching your current search terms or filter combinations.
        </p>
        {hasActiveFilters && onClearFilters && (
          <div className="empty-actions">
            <button type="button" className="btn btn-secondary" onClick={onClearFilters}>
              Clear All Filters
            </button>
          </div>
        )}

        <style>{`
          .recipe-grid-empty {
            padding: var(--space-8);
            background-color: var(--color-surface);
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: var(--space-3);
          }

          .empty-heading {
            font-size: var(--text-xl);
            font-family: var(--font-serif);
            margin-top: var(--space-1);
          }

          .empty-message {
            font-size: var(--text-sm);
            color: var(--color-text-secondary);
            max-width: 600px;
          }

          .empty-actions {
            margin-top: var(--space-2);
          }
        `}</style>
      </div>
    );
  }

  // 4. Results Grid
  return (
    <div className="recipe-grid-container">
      <div className="recipe-cards-grid" role="feed" aria-label="Recipe search results">
        {recipes.map((recipe) => (
          <RecipeCard key={recipe.id} recipe={recipe} />
        ))}
      </div>

      <style>{`
        .recipe-grid-container {
          width: 100%;
        }

        .recipe-cards-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: var(--space-6);
        }
      `}</style>
    </div>
  );
};

