import React from 'react';
import { useRecipeSearch } from '../hooks/useRecipeSearch';
import { RecipeSearchBar } from '../components/recipes/RecipeSearchBar';
import { RecipeFilters } from '../components/recipes/RecipeFilters';
import { RecipeSortControl } from '../components/recipes/RecipeSortControl';
import { RecipeGrid } from '../components/recipes/RecipeGrid';
import { RecipePagination } from '../components/recipes/RecipePagination';

export const RecipeDiscoveryPage: React.FC = () => {
  const {
    recipes,
    pagination,
    loading,
    error,
    queryInput,
    setQueryInput,
    activeQuery,
    activeFilters,
    activeSort,
    submitSearch,
    clearSearch,
    setFilter,
    removeFilter,
    clearAllFilters,
    setSort,
    setPage,
    retry,
  } = useRecipeSearch(24);

  const hasActiveFilters = Boolean(
    activeQuery ||
      activeFilters.cuisine ||
      activeFilters.diet ||
      activeFilters.tag ||
      activeFilters.max_time ||
      activeFilters.source_dataset
  );

  return (
    <div className="container discovery-page-container">
      {/* Editorial Page Header */}
      <header className="discovery-header">
        <span className="editorial-badge">Catalogue Explorer</span>
        <h1 className="discovery-title">Recipe Discovery &amp; Culinary Search</h1>
        <p className="discovery-lead">
          Explore 50,000 verified culinary preparations from Food.com and RecipeNLG.
          Filter by cuisine, dietary category, or preparation duration powered by PostgreSQL full-text search.
        </p>
      </header>

      {/* Search Input Bar */}
      <section className="search-section" aria-label="Search recipes">
        <RecipeSearchBar
          value={queryInput}
          onChange={setQueryInput}
          onSubmit={() => submitSearch()}
          onClear={clearSearch}
          loading={loading}
        />
      </section>

      {/* Filter Controls Accordion / Panel */}
      <section className="filters-section" aria-label="Filter recipe catalog">
        <RecipeFilters
          filters={activeFilters}
          onSetFilter={setFilter}
          onRemoveFilter={removeFilter}
          onClearAll={clearAllFilters}
          disabled={loading}
        />
      </section>

      {/* Controls & Metrics Header Row */}
      <div className="discovery-controls-row">
        <div className="results-count-metric" aria-live="polite">
          {!loading && !error && (
            <span>
              Found <strong>{pagination.total_items.toLocaleString()}</strong>{' '}
              {pagination.total_items === 1 ? 'recipe' : 'recipes'}
              {activeQuery && (
                <span>
                  {' '}
                  matching &ldquo;<em>{activeQuery}</em>&rdquo;
                </span>
              )}
            </span>
          )}
        </div>

        <div className="sort-controls-container">
          <RecipeSortControl
            value={activeSort}
            onChange={setSort}
            disabled={loading}
          />
        </div>
      </div>

      {/* Results Grid with Loading / Empty / Error Handling */}
      <section className="results-grid-section" aria-label="Recipe search results">
        <RecipeGrid
          recipes={recipes}
          loading={loading}
          error={error}
          onRetry={retry}
          onClearFilters={clearAllFilters}
          hasActiveFilters={hasActiveFilters}
        />
      </section>

      {/* Bottom Pagination Controls */}
      {!loading && !error && recipes.length > 0 && (
        <section className="pagination-section">
          <RecipePagination
            pagination={pagination}
            onPageChange={setPage}
            disabled={loading}
          />
        </section>
      )}

      <style>{`
        .discovery-page-container {
          padding-top: var(--space-8);
          padding-bottom: var(--space-12);
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }

        .discovery-header {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: var(--space-2);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-6);
        }

        .discovery-title {
          font-size: var(--text-3xl);
          font-weight: 700;
          margin-top: var(--space-1);
        }

        .discovery-lead {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
          max-width: 800px;
          line-height: 1.6;
        }

        .search-section {
          width: 100%;
        }

        .filters-section {
          width: 100%;
        }

        .discovery-controls-row {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: var(--space-3);
          padding-bottom: var(--space-2);
          border-bottom: 1px solid var(--color-border);
        }

        .results-count-metric {
          font-family: var(--font-sans);
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .results-count-metric strong {
          color: var(--color-text-primary);
        }

        .sort-controls-container {
          margin-left: auto;
        }

        .results-grid-section {
          width: 100%;
          min-height: 300px;
        }

        .pagination-section {
          width: 100%;
        }
      `}</style>
    </div>
  );
};
