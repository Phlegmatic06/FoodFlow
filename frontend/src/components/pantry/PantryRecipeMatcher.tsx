import React, { useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { plannerClient } from '../../api/plannerClient';
import { PantryMatchRequest, PantryMatchResponse, PantryMatchResultItem } from '../../api/types/planner';

interface PantryRecipeMatcherProps {
  pantryItemCount: number;
  sessionId?: string;
  onSessionExpired?: () => Promise<string>;
}

export const PantryRecipeMatcher: React.FC<PantryRecipeMatcherProps> = ({
  pantryItemCount,
  sessionId,
  onSessionExpired,
}) => {
  const [excludeStaples, setExcludeStaples] = useState<boolean>(true);
  const [minMatchPct, setMinMatchPct] = useState<number>(30);

  const [matches, setMatches] = useState<PantryMatchResultItem[]>([]);
  const [totalItems, setTotalItems] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(0);

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [hasExecutedMatch, setHasExecutedMatch] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  const executeMatch = useCallback(
    async (currentPage = 1, currentSessionId = sessionId) => {
      if (pantryItemCount === 0) {
        setError('Your pantry is empty. Add ingredients above before matching recipes.');
        return;
      }

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setIsLoading(true);
      setError(null);
      setHasExecutedMatch(true);

      const requestPayload: PantryMatchRequest = {
        exclude_pantry_staples: excludeStaples,
        min_match_pct: minMatchPct,
        page: currentPage,
        limit: 12,
      };

      try {
        const response: PantryMatchResponse = await plannerClient.matchPantry(
          requestPayload,
          currentSessionId,
          { signal: controller.signal }
        );

        // Handle both `matches` and `data` defensively
        const resultItems = response.matches || response.data || [];
        setMatches(resultItems);
        setPage(response.pagination?.page || 1);
        setTotalPages(response.pagination?.total_pages || 0);
        setTotalItems(response.pagination?.total_items || 0);
      } catch (err: unknown) {
        if (controller.signal.aborted) return;

        // Check for session expired (401)
        const isSessionExpiredError =
          (err as { statusCode?: number })?.statusCode === 401 ||
          (err as { status?: number })?.status === 401 ||
          /session_expired|expired/i.test(err instanceof Error ? err.message : '');

        if (isSessionExpiredError && onSessionExpired) {
          try {
            const newSessionId = await onSessionExpired();
            // Retry once with new session
            return executeMatch(currentPage, newSessionId);
          } catch {
            // recovery failed
          }
        }

        setError(
          err instanceof Error
            ? err.message
            : 'Failed to find matching recipes from pantry ingredients.'
        );
        setMatches([]);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    },
    [pantryItemCount, excludeStaples, minMatchPct, sessionId, onSessionExpired]
  );

  const handleMatchClick = () => {
    executeMatch(1);
  };

  const getMatchScoreBadgeClass = (score: number) => {
    if (score >= 80) return 'match-high';
    if (score >= 50) return 'match-med';
    return 'match-low';
  };

  return (
    <section className="editorial-card matcher-card" data-testid="pantry-recipe-matcher-section">
      <div className="matcher-header-strip">
        <div>
          <span className="editorial-badge">Catalogue Reconciliation</span>
          <h2 className="matcher-title" data-testid="matcher-heading">
            Recipe Overlap Matching Engine
          </h2>
        </div>
      </div>

      <p className="matcher-desc">
        Calculate ingredient overlap against our 50,000-recipe catalog. Discover viable meals you
        can prepare with your saved pantry ingredients and identify any missing items.
      </p>

      {/* Controls Bar */}
      <div className="matcher-controls-bar">
        <div className="control-group staple-toggle-group">
          <label className="checkbox-label" htmlFor="staple-exclude-toggle">
            <input
              id="staple-exclude-toggle"
              type="checkbox"
              className="form-checkbox"
              checked={excludeStaples}
              onChange={(e) => setExcludeStaples(e.target.checked)}
              data-testid="staple-exclusion-checkbox"
            />
            <span className="checkbox-text">
              Exclude basic staples from denominator{' '}
              <span className="staple-subtext">(salt, black pepper, water)</span>
            </span>
          </label>
        </div>

        <div className="control-group threshold-group">
          <label htmlFor="min-match-select" className="threshold-label">
            Min Match:
          </label>
          <select
            id="min-match-select"
            className="form-select threshold-select"
            value={minMatchPct}
            onChange={(e) => setMinMatchPct(Number(e.target.value))}
            data-testid="min-match-select"
          >
            <option value="20">20% Minimum Overlap</option>
            <option value="30">30% Minimum Overlap (Recommended)</option>
            <option value="50">50% Minimum Overlap</option>
            <option value="75">75% High Overlap</option>
          </select>
        </div>

        <button
          type="button"
          className="btn btn-primary btn-find-recipes"
          onClick={handleMatchClick}
          disabled={isLoading || pantryItemCount === 0}
          data-testid="find-recipes-btn"
        >
          {isLoading ? 'Reconciling Recipes...' : 'Find Matching Recipes →'}
        </button>
      </div>

      {pantryItemCount === 0 && (
        <div className="empty-pantry-notice" data-testid="empty-pantry-matcher-notice">
          <span>Add at least one ingredient to your pantry above to search for matching recipes.</span>
        </div>
      )}

      {/* Results Area */}
      {isLoading ? (
        <div className="matcher-status-box loading-box" data-testid="matcher-loading">
          <p>
            Reconciling verified canonical pantry items across recipe catalog records via Planner Service (:8003)...
          </p>
        </div>
      ) : error ? (
        <div className="matcher-status-box error-box" role="alert" data-testid="matcher-error">
          <span className="editorial-badge error-badge">Matching Failed</span>
          <p className="error-msg">{error}</p>
          <button
            type="button"
            className="btn btn-secondary btn-retry"
            onClick={() => executeMatch(page)}
            data-testid="matcher-retry-btn"
          >
            Retry Matching
          </button>
        </div>
      ) : hasExecutedMatch && matches.length === 0 ? (
        <div className="matcher-status-box empty-box" data-testid="matcher-empty-results">
          <span className="editorial-badge">Zero Candidates</span>
          <h3 className="empty-results-title">No Matching Recipes Found</h3>
          <p className="empty-results-desc">
            No recipes in the catalog met the {minMatchPct}% ingredient overlap threshold with your
            current pantry inventory. Try lowering the match threshold or adding more pantry items.
          </p>
        </div>
      ) : matches.length > 0 ? (
        <div className="matches-container" data-testid="matches-container">
          <div className="matches-summary-strip">
            <span className="matches-count-label" data-testid="matches-count-label">
              Found {totalItems} {totalItems === 1 ? 'recipe candidate' : 'recipe candidates'} ({matches.length} displayed)
            </span>
            <span className="match-score-explainer">
              Match score = verified pantry overlap / tracked recipe ingredients
            </span>
          </div>

          <div className="matches-grid" data-testid="matches-grid">
            {matches.map((item) => (
              <article
                key={item.recipe_id}
                className="editorial-card recipe-match-card"
                data-testid={`match-card-${item.recipe_id}`}
              >
                <div className="match-card-top">
                  <span className="recipe-global-id">{item.recipe_id}</span>
                  <span
                    className={`editorial-badge match-pct-badge ${getMatchScoreBadgeClass(item.match_pct)}`}
                    data-testid={`match-score-${item.recipe_id}`}
                  >
                    {item.match_pct.toFixed(0)}% Match
                  </span>
                </div>

                <h3 className="match-recipe-title">
                  <Link
                    to={`/recipes/${item.recipe_id}`}
                    className="match-recipe-link"
                    data-testid={`recipe-link-${item.recipe_id}`}
                  >
                    {item.title}
                  </Link>
                </h3>

                <div className="match-recipe-meta">
                  {item.total_time_minutes && (
                    <span className="meta-time">⏱ {item.total_time_minutes} mins</span>
                  )}
                  {item.rating_average && (
                    <span className="meta-rating">★ {item.rating_average.toFixed(1)}</span>
                  )}
                  <span className="meta-ingredients">
                    {item.total_recipe_ingredients} total ingredients
                  </span>
                </div>

                {/* Overlap Ingredients Breakdown */}
                <div className="ingredients-breakdown-box">
                  {item.matched_ingredients.length > 0 && (
                    <div className="matched-ingredients-section" data-testid={`matched-list-${item.recipe_id}`}>
                      <span className="breakdown-label label-matched">
                        ✓ In Your Pantry ({item.matched_ingredients.length}):
                      </span>
                      <ul className="breakdown-list matched-items-list">
                        {item.matched_ingredients.map((ing, idx) => (
                          <li key={idx} className="matched-tag">
                            {ing}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {item.missing_ingredients.length > 0 && (
                    <div className="missing-ingredients-section" data-testid={`missing-list-${item.recipe_id}`}>
                      <span className="breakdown-label label-missing">
                        Missing ({item.missing_ingredients.length}):
                      </span>
                      <ul className="breakdown-list missing-items-list">
                        {item.missing_ingredients.map((ing, idx) => (
                          <li key={idx} className="missing-tag">
                            {ing}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="match-card-footer">
                  <Link
                    to={`/recipes/${item.recipe_id}`}
                    className="btn btn-secondary view-recipe-btn"
                    data-testid={`view-recipe-btn-${item.recipe_id}`}
                  >
                    View Recipe &amp; Cook Mode &rarr;
                  </Link>
                </div>
              </article>
            ))}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="matcher-pagination-bar" data-testid="matcher-pagination">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1 || isLoading}
                onClick={() => executeMatch(page - 1)}
                data-testid="matcher-prev-page-btn"
              >
                &larr; Previous Page
              </button>
              <span className="page-indicator" data-testid="matcher-page-indicator">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page >= totalPages || isLoading}
                onClick={() => executeMatch(page + 1)}
                data-testid="matcher-next-page-btn"
              >
                Next Page &rarr;
              </button>
            </div>
          )}
        </div>
      ) : null}

      <style>{`
        .matcher-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-6);
        }

        .matcher-header-strip {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-3);
        }

        .matcher-title {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .matcher-desc {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          line-height: 1.5;
        }

        .matcher-controls-bar {
          display: flex;
          align-items: center;
          gap: var(--space-4);
          flex-wrap: wrap;
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          padding: var(--space-3) var(--space-4);
        }

        .staple-toggle-group {
          display: flex;
          align-items: center;
        }

        .checkbox-label {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          font-size: var(--text-xs);
          font-weight: 600;
          cursor: pointer;
        }

        .staple-subtext {
          font-weight: normal;
          color: var(--color-text-muted);
        }

        .threshold-group {
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }

        .threshold-label {
          font-size: var(--text-xs);
          font-weight: 600;
          color: var(--color-text-secondary);
        }

        .threshold-select {
          font-size: var(--text-xs);
          padding: var(--space-1) var(--space-2);
        }

        .btn-find-recipes {
          margin-left: auto;
          font-weight: 600;
        }

        .empty-pantry-notice {
          padding: var(--space-3);
          background-color: var(--color-surface-subtle);
          border-left: 3px solid var(--color-border-strong);
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .matcher-status-box {
          padding: var(--space-6);
          border: 1px solid var(--color-border);
          background-color: var(--color-surface-subtle);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          align-items: flex-start;
          font-size: var(--text-sm);
        }

        .empty-box {
          align-items: flex-start;
        }

        .empty-results-title {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .empty-results-desc {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .matches-container {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          margin-top: var(--space-2);
        }

        .matches-summary-strip {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: var(--space-2);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-2);
        }

        .matches-count-label {
          font-size: var(--text-sm);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .match-score-explainer {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          font-style: italic;
        }

        .matches-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-4);
        }

        @media (min-width: 768px) {
          .matches-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        .recipe-match-card {
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .match-card-top {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .recipe-global-id {
          font-family: var(--font-mono);
          font-size: var(--text-xs);
          color: var(--color-text-muted);
        }

        .match-pct-badge {
          font-weight: 700;
        }

        .match-high {
          background-color: var(--color-success-subtle);
          color: var(--color-success);
          border-color: var(--color-success);
        }

        .match-med {
          background-color: var(--color-surface-subtle);
          color: var(--color-accent);
          border-color: var(--color-accent);
        }

        .match-low {
          background-color: var(--color-surface-subtle);
          color: var(--color-text-secondary);
        }

        .match-recipe-title {
          font-family: var(--font-serif);
          font-size: var(--text-lg);
          font-weight: 700;
          line-height: 1.3;
        }

        .match-recipe-link {
          color: var(--color-text-primary);
          text-decoration: none;
        }

        .match-recipe-link:hover {
          color: var(--color-accent);
          text-decoration: underline;
        }

        .match-recipe-meta {
          display: flex;
          gap: var(--space-3);
          font-size: var(--text-xs);
          color: var(--color-text-muted);
          flex-wrap: wrap;
        }

        .ingredients-breakdown-box {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          padding: var(--space-3);
          font-size: var(--text-xs);
        }

        .breakdown-label {
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          margin-bottom: var(--space-1);
          display: block;
        }

        .label-matched {
          color: var(--color-success);
        }

        .label-missing {
          color: var(--color-error);
        }

        .breakdown-list {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
        }

        .matched-tag {
          background-color: var(--color-success-subtle);
          border: 1px solid var(--color-success);
          color: var(--color-text-primary);
          padding: 1px 6px;
        }

        .missing-tag {
          background-color: var(--color-surface);
          border: 1px dashed var(--color-border-strong);
          color: var(--color-text-secondary);
          padding: 1px 6px;
        }

        .match-card-footer {
          margin-top: auto;
          padding-top: var(--space-2);
        }

        .view-recipe-btn {
          width: 100%;
          justify-content: center;
          font-size: var(--text-xs);
        }

        .matcher-pagination-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-top: 1px solid var(--color-border);
          padding-top: var(--space-4);
        }

        .page-indicator {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }
      `}</style>
    </section>
  );
};

