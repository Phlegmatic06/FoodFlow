import React, { useState, useCallback, useRef } from 'react';
import { profileClient } from '../../api/profileClient';
import { USDAFoodDetail, USDAFoodSummary } from '../../api/types/profile';

export const USDAFoodExplorer: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [activeQuery, setActiveQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<USDAFoodSummary[]>([]);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [totalItems, setTotalItems] = useState<number>(0);

  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Selected food detail
  const [selectedFood, setSelectedFood] = useState<USDAFoodDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // AbortController for stale-request protection
  const searchAbortRef = useRef<AbortController | null>(null);
  const detailAbortRef = useRef<AbortController | null>(null);

  const executeSearch = useCallback(
    async (queryText: string, targetPage: number = 1) => {
      const clean = queryText.trim();
      if (!clean) return;

      if (searchAbortRef.current) {
        searchAbortRef.current.abort();
      }
      const controller = new AbortController();
      searchAbortRef.current = controller;

      setIsSearching(true);
      setSearchError(null);
      setActiveQuery(clean);

      try {
        const response = await profileClient.searchFoods(clean, 10, targetPage, {
          signal: controller.signal,
        });
        setSearchResults(response.data);
        setPage(response.pagination.page);
        setTotalPages(response.pagination.total_pages);
        setTotalItems(response.pagination.total_items);
      } catch (err: unknown) {
        if (controller.signal.aborted) return;
        setSearchError(
          err instanceof Error ? err.message : 'Failed to query USDA FoodData Central.'
        );
      } finally {
        if (!controller.signal.aborted) {
          setIsSearching(false);
        }
      }
    },
    []
  );

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(searchTerm, 1);
  };

  const handleSelectFood = useCallback(async (fdcId: number) => {
    if (detailAbortRef.current) {
      detailAbortRef.current.abort();
    }
    const controller = new AbortController();
    detailAbortRef.current = controller;

    setIsLoadingDetail(true);
    setDetailError(null);

    try {
      const detail = await profileClient.getFoodDetail(fdcId, {
        signal: controller.signal,
      });
      setSelectedFood(detail);
    } catch (err: unknown) {
      if (controller.signal.aborted) return;
      setDetailError(
        err instanceof Error ? err.message : `Failed to load details for FDC item ${fdcId}.`
      );
    } finally {
      if (!controller.signal.aborted) {
        setIsLoadingDetail(false);
      }
    }
  }, []);

  const formatAmount = (val: number | null | undefined, unit: string) => {
    if (val === null || val === undefined) {
      return <span className="val-unavailable">Unavailable</span>;
    }
    // Format nicely without turning null into 0.00
    const formatted = Number.isInteger(val) ? val.toString() : val.toFixed(2);
    return (
      <span className="val-numeric">
        {formatted} <span className="val-unit">{unit}</span>
      </span>
    );
  };

  return (
    <section className="usda-explorer-section" data-testid="usda-food-explorer-section">
      <div className="section-header-block">
        <span className="editorial-badge">USDA FoodData Central</span>
        <h2 className="section-title" data-testid="usda-heading">
          USDA SR Legacy Food &amp; Nutrient Explorer
        </h2>
        <p className="section-lead">
          Query empirical laboratory nutritional measurements from the USDA Standard Reference Legacy
          ground truth database. Every entry retains verified nutrient amounts per 100g edible
          portion and standard household volumetric portion mappings.
        </p>
      </div>

      <div className="usda-content-layout">
        {/* Search & Results Panel */}
        <div className="usda-search-column">
          <form
            className="editorial-card usda-search-form"
            onSubmit={handleSearchSubmit}
            data-testid="usda-search-form"
          >
            <div className="search-bar-row">
              <input
                type="text"
                className="form-input search-input"
                placeholder="Search USDA food descriptions (e.g. rolled oats, chicken breast, olive oil)..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                required
                data-testid="usda-search-input"
                aria-label="Search USDA foods"
              />
              <button
                type="submit"
                className="btn btn-primary btn-search-usda"
                disabled={isSearching}
                data-testid="usda-search-btn"
              >
                {isSearching ? 'Searching...' : 'Search →'}
              </button>
            </div>
            <div className="quick-examples">
              <span className="examples-label">Try:</span>
              {['oats', 'chicken breast', 'spinach', 'cheddar cheese', 'salmon'].map((term) => (
                <button
                  key={term}
                  type="button"
                  className="quick-term-btn"
                  onClick={() => {
                    setSearchTerm(term);
                    executeSearch(term, 1);
                  }}
                  data-testid={`quick-usda-${term.replace(/\s+/g, '-')}`}
                >
                  {term}
                </button>
              ))}
            </div>
          </form>

          {/* Search Status & Results List */}
          <div className="usda-results-container" data-testid="usda-results-container">
            {isSearching && (
              <div className="editorial-card status-card" data-testid="usda-search-loading">
                <p>Querying USDA FoodData Central (:8001)...</p>
              </div>
            )}

            {searchError && (
              <div className="editorial-card error-card" data-testid="usda-search-error">
                <span className="editorial-badge error-badge">Query Error</span>
                <p className="error-text">{searchError}</p>
                <button
                  type="button"
                  className="btn btn-secondary btn-retry"
                  onClick={() => executeSearch(activeQuery, page)}
                  data-testid="usda-retry-btn"
                >
                  Retry Search
                </button>
              </div>
            )}

            {!isSearching && !searchError && activeQuery && searchResults.length === 0 && (
              <div className="editorial-card empty-results-card" data-testid="usda-empty-results">
                <h3 className="empty-title">No USDA Foods Found</h3>
                <p className="empty-text">
                  No items in the USDA SR Legacy index matched &ldquo;{activeQuery}&rdquo;. Try
                  searching for standard base food terms (e.g., &ldquo;egg&rdquo;, &ldquo;milk&rdquo;,
                  &ldquo;rice&rdquo;).
                </p>
              </div>
            )}

            {!isSearching && searchResults.length > 0 && (
              <div className="results-wrapper">
                <div className="results-meta-strip">
                  <span className="results-count" data-testid="usda-results-count">
                    {totalItems} items matching &ldquo;{activeQuery}&rdquo;
                  </span>
                  <span className="results-page">
                    Page {page} of {totalPages}
                  </span>
                </div>

                <ul className="usda-items-list" data-testid="usda-foods-list">
                  {searchResults.map((item) => {
                    const isSelected = selectedFood?.fdc_id === item.fdc_id;

                    return (
                      <li
                        key={item.fdc_id}
                        className={`usda-item-card ${isSelected ? 'selected-item' : ''}`}
                        onClick={() => handleSelectFood(item.fdc_id)}
                        data-testid={`usda-item-${item.fdc_id}`}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            handleSelectFood(item.fdc_id);
                          }
                        }}
                      >
                        <div className="item-main-info">
                          <span className="item-description">{item.description}</span>
                          <div className="item-meta">
                            <span className="fdc-badge">FDC #{item.fdc_id}</span>
                            <span className="type-badge">{item.data_type}</span>
                          </div>
                        </div>
                        <span className="view-detail-arrow">&rarr;</span>
                      </li>
                    );
                  })}
                </ul>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="pagination-bar" data-testid="usda-pagination">
                    <button
                      type="button"
                      className="btn btn-secondary pagination-btn"
                      disabled={page <= 1}
                      onClick={() => executeSearch(activeQuery, page - 1)}
                      data-testid="usda-prev-page"
                    >
                      &larr; Prev
                    </button>
                    <span className="page-indicator" data-testid="usda-page-indicator">
                      {page} / {totalPages}
                    </span>
                    <button
                      type="button"
                      className="btn btn-secondary pagination-btn"
                      disabled={page >= totalPages}
                      onClick={() => executeSearch(activeQuery, page + 1)}
                      data-testid="usda-next-page"
                    >
                      Next &rarr;
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Selected Food Detail Column */}
        <div className="usda-detail-column" data-testid="usda-detail-column">
          {isLoadingDetail ? (
            <div className="editorial-card detail-loading-card" data-testid="food-detail-loading">
              <p>Fetching complete nutrient profile from Profile Service...</p>
            </div>
          ) : detailError ? (
            <div className="editorial-card error-card" data-testid="food-detail-error">
              <span className="editorial-badge error-badge">Detail Error</span>
              <p className="error-text">{detailError}</p>
            </div>
          ) : !selectedFood ? (
            <div className="editorial-card detail-placeholder-card" data-testid="detail-placeholder">
              <span className="editorial-badge">Laboratory Breakdown</span>
              <h3 className="placeholder-title">Select a Food Item</h3>
              <p className="placeholder-text">
                Click any USDA food from the search results to inspect its complete analytical
                nutrient breakdown per 100g and household portion metrics.
              </p>
            </div>
          ) : (
            <div className="editorial-card food-detail-card" data-testid="food-detail-card">
              <div className="detail-header-strip">
                <div>
                  <span className="editorial-badge">FDC ID #{selectedFood.fdc_id}</span>
                  <h3 className="selected-food-title" data-testid="selected-food-title">
                    {selectedFood.description}
                  </h3>
                  <span className="selected-food-type">Dataset: {selectedFood.data_type}</span>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-close-detail"
                  onClick={() => setSelectedFood(null)}
                  data-testid="close-food-detail-btn"
                  title="Close Detail"
                >
                  &times;
                </button>
              </div>

              {/* Portion Metrics */}
              {selectedFood.portions && selectedFood.portions.length > 0 && (
                <div className="portions-container" data-testid="food-portions-list">
                  <h4 className="sub-heading">Household Portion Mappings</h4>
                  <div className="portions-grid">
                    {selectedFood.portions.map((portion) => (
                      <div key={portion.id} className="portion-chip" data-testid={`portion-${portion.id}`}>
                        <span className="portion-desc">
                          {portion.amount ? `${portion.amount} ` : ''}
                          {portion.portion_description || portion.modifier || 'Standard Unit'}
                        </span>
                        <span className="portion-weight">({portion.gram_weight}g)</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Nutrients Table */}
              <div className="nutrients-table-wrapper" data-testid="nutrients-table-wrapper">
                <h4 className="sub-heading">Analytical Nutrients (per 100g edible portion)</h4>
                <table className="editorial-table nutrients-table" data-testid="nutrients-table">
                  <thead>
                    <tr>
                      <th scope="col">Nutrient Name</th>
                      <th scope="col" className="col-num">
                        Amount / 100g
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedFood.nutrients && selectedFood.nutrients.length > 0 ? (
                      selectedFood.nutrients.map((n) => (
                        <tr key={n.nutrient_id} data-testid={`nutrient-row-${n.nutrient_id}`}>
                          <td className="nutrient-cell-name">
                            {n.name}
                            <span className="id-sub">#{n.nutrient_id}</span>
                          </td>
                          <td className="nutrient-cell-amount col-num">
                            {formatAmount(n.amount_per_100g, n.unit_name)}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={2} className="no-nutrients-cell">
                          No nutrient measurements recorded.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        .usda-explorer-section {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
        }

        .section-header-block {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-4);
        }

        .section-title {
          font-size: var(--text-2xl);
          font-weight: 700;
        }

        .section-lead {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          max-width: 800px;
          line-height: 1.6;
        }

        .usda-content-layout {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-6);
        }

        @media (min-width: 900px) {
          .usda-content-layout {
            grid-template-columns: 1.1fr 1fr;
          }
        }

        .usda-search-column {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .usda-search-form {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          background-color: var(--color-surface);
        }

        .search-bar-row {
          display: flex;
          gap: var(--space-2);
        }

        .search-input {
          flex: 1;
        }

        .quick-examples {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          flex-wrap: wrap;
        }

        .examples-label {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-weight: 700;
          text-transform: uppercase;
        }

        .quick-term-btn {
          font-size: 0.72rem;
          color: var(--color-accent);
          background-color: var(--color-accent-subtle);
          padding: 0.1rem 0.4rem;
          border: 1px solid var(--color-accent);
          cursor: pointer;
        }

        .quick-term-btn:hover {
          background-color: var(--color-accent);
          color: #ffffff;
        }

        .status-card, .error-card, .empty-results-card {
          padding: var(--space-4);
          background-color: var(--color-surface);
        }

        .error-badge {
          background-color: var(--color-error-subtle);
          color: var(--color-error);
          align-self: flex-start;
          margin-bottom: var(--space-2);
        }

        .error-text {
          font-size: var(--text-sm);
          color: var(--color-error);
        }

        .btn-retry {
          margin-top: var(--space-2);
          font-size: var(--text-xs);
        }

        .empty-title {
          font-size: var(--text-base);
          font-family: var(--font-serif);
          margin-bottom: var(--space-1);
        }

        .empty-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .results-wrapper {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .results-meta-strip {
          display: flex;
          justify-content: space-between;
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .usda-items-list {
          list-style: none;
          display: flex;
          flex-direction: column;
          gap: 1px;
          background-color: var(--color-border);
          border: 1px solid var(--color-border);
        }

        .usda-item-card {
          background-color: var(--color-surface);
          padding: var(--space-3) var(--space-4);
          display: flex;
          justify-content: space-between;
          align-items: center;
          cursor: pointer;
          transition: background-color var(--transition-fast);
        }

        .usda-item-card:hover {
          background-color: var(--color-surface-hover);
        }

        .usda-item-card.selected-item {
          border-left: 4px solid var(--color-accent);
          background-color: var(--color-accent-subtle);
        }

        .item-main-info {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .item-description {
          font-size: var(--text-sm);
          font-weight: 600;
          color: var(--color-text-primary);
        }

        .item-meta {
          display: flex;
          gap: var(--space-2);
        }

        .fdc-badge {
          font-family: var(--font-mono);
          font-size: 0.7rem;
          color: var(--color-accent);
        }

        .type-badge {
          font-size: 0.7rem;
          color: var(--color-text-muted);
        }

        .view-detail-arrow {
          font-size: var(--text-base);
          color: var(--color-text-muted);
        }

        .pagination-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: var(--space-2);
        }

        .pagination-btn {
          font-size: var(--text-xs);
          padding: var(--space-1) var(--space-3);
        }

        .page-indicator {
          font-family: var(--font-mono);
          font-size: var(--text-xs);
        }

        /* Detail Column */
        .detail-placeholder-card, .detail-loading-card, .food-detail-card {
          height: 100%;
          padding: var(--space-6);
          background-color: var(--color-surface);
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
        }

        .detail-header-strip {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-3);
        }

        .selected-food-title {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          margin-top: var(--space-1);
        }

        .selected-food-type {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
        }

        .btn-close-detail {
          padding: 0.1rem 0.5rem;
          font-size: var(--text-lg);
          line-height: 1;
        }

        .sub-heading {
          font-size: var(--text-xs);
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--color-text-muted);
          margin-bottom: var(--space-2);
        }

        .portions-grid {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
        }

        .portion-chip {
          display: inline-flex;
          gap: var(--space-1);
          padding: var(--space-1) var(--space-2);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          font-size: var(--text-xs);
        }

        .portion-weight {
          color: var(--color-accent);
          font-weight: 600;
        }

        .nutrients-table-wrapper {
          overflow-x: auto;
          max-height: 450px;
          overflow-y: auto;
          border: 1px solid var(--color-border);
        }

        .nutrients-table {
          width: 100%;
          border-collapse: collapse;
          font-size: var(--text-xs);
        }

        .nutrients-table th {
          background-color: var(--color-surface-subtle);
          padding: var(--space-2) var(--space-3);
          text-align: left;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          border-bottom: 1px solid var(--color-border);
          position: sticky;
          top: 0;
          z-index: 1;
        }

        .nutrients-table td {
          padding: var(--space-2) var(--space-3);
          border-bottom: 1px solid var(--color-border);
        }

        .col-num {
          text-align: right;
        }

        .id-sub {
          font-size: 0.65rem;
          color: var(--color-text-muted);
          margin-left: var(--space-1);
        }

        .val-numeric {
          font-weight: 600;
          color: var(--color-text-primary);
        }

        .val-unit {
          font-weight: 400;
          color: var(--color-text-muted);
        }

        .val-unavailable {
          color: var(--color-text-muted);
          font-style: italic;
        }
      `}</style>
    </section>
  );
};

