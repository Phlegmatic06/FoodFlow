import React from 'react';
import { PaginationInfo } from '../../api/types/recipe';

interface RecipePaginationProps {
  pagination: PaginationInfo;
  onPageChange: (newPage: number) => void;
  disabled?: boolean;
}

export const RecipePagination: React.FC<RecipePaginationProps> = ({
  pagination,
  onPageChange,
  disabled = false,
}) => {
  const { page, limit, total_items, total_pages } = pagination;

  if (total_pages <= 1) {
    return null;
  }

  const startItem = total_items === 0 ? 0 : (page - 1) * limit + 1;
  const endItem = Math.min(page * limit, total_items);

  const canPrev = page > 1;
  const canNext = page < total_pages;

  // Generate a compact window of visible page numbers
  const getPageNumbers = (): number[] => {
    const pages: number[] = [];
    const maxVisible = 5;
    let start = Math.max(1, page - Math.floor(maxVisible / 2));
    const end = Math.min(total_pages, start + maxVisible - 1);

    if (end - start + 1 < maxVisible) {
      start = Math.max(1, end - maxVisible + 1);
    }

    for (let p = start; p <= end; p++) {
      pages.push(p);
    }
    return pages;
  };

  const visiblePages = getPageNumbers();

  return (
    <nav className="recipe-pagination" aria-label="Recipe search pagination">
      <div className="pagination-summary">
        Showing <strong>{startItem}</strong>&ndash;<strong>{endItem}</strong> of{' '}
        <strong>{total_items.toLocaleString()}</strong> recipes
      </div>

      <div className="pagination-controls">
        <button
          type="button"
          className="btn btn-secondary pagination-btn"
          onClick={() => onPageChange(page - 1)}
          disabled={!canPrev || disabled}
          aria-label="Previous page"
        >
          &larr; Prev
        </button>

        <div className="page-numbers-group" role="group" aria-label="Page selection">
          {visiblePages[0] > 1 && (
            <>
              <button
                type="button"
                className="page-number-btn"
                onClick={() => onPageChange(1)}
                disabled={disabled}
                aria-label="Go to page 1"
              >
                1
              </button>
              {visiblePages[0] > 2 && <span className="page-ellipsis" aria-hidden="true">&hellip;</span>}
            </>
          )}

          {visiblePages.map((p) => (
            <button
              key={p}
              type="button"
              className={`page-number-btn ${p === page ? 'page-number-active' : ''}`}
              onClick={() => onPageChange(p)}
              disabled={disabled}
              aria-current={p === page ? 'page' : undefined}
              aria-label={`Go to page ${p}`}
            >
              {p}
            </button>
          ))}

          {visiblePages[visiblePages.length - 1] < total_pages && (
            <>
              {visiblePages[visiblePages.length - 1] < total_pages - 1 && (
                <span className="page-ellipsis" aria-hidden="true">&hellip;</span>
              )}
              <button
                type="button"
                className="page-number-btn"
                onClick={() => onPageChange(total_pages)}
                disabled={disabled}
                aria-label={`Go to page ${total_pages}`}
              >
                {total_pages}
              </button>
            </>
          )}
        </div>

        <button
          type="button"
          className="btn btn-secondary pagination-btn"
          onClick={() => onPageChange(page + 1)}
          disabled={!canNext || disabled}
          aria-label="Next page"
        >
          Next &rarr;
        </button>
      </div>

      <style>{`
        .recipe-pagination {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: var(--space-4);
          padding-top: var(--space-6);
          border-top: 1px solid var(--color-border);
          margin-top: var(--space-6);
        }

        .pagination-summary {
          font-family: var(--font-sans);
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .pagination-summary strong {
          color: var(--color-text-primary);
        }

        .pagination-controls {
          display: flex;
          align-items: center;
          gap: var(--space-2);
        }

        .pagination-btn {
          padding: var(--space-2) var(--space-4);
          font-size: var(--text-xs);
        }

        .page-numbers-group {
          display: flex;
          align-items: center;
          gap: var(--space-1);
        }

        .page-number-btn {
          min-width: 32px;
          height: 32px;
          padding: 0 var(--space-2);
          display: inline-flex;
          align-items: center;
          justify-content: center;
          font-family: var(--font-mono);
          font-size: var(--text-xs);
          background-color: var(--color-surface);
          color: var(--color-text-primary);
          border: 1px solid var(--color-border);
          cursor: pointer;
          transition: background-color var(--transition-fast), border-color var(--transition-fast);
        }

        .page-number-btn:hover:not(:disabled) {
          border-color: var(--color-accent);
          color: var(--color-accent);
        }

        .page-number-active {
          background-color: var(--color-accent);
          color: var(--color-accent-text);
          border-color: var(--color-accent);
          font-weight: 700;
        }

        .page-ellipsis {
          color: var(--color-text-muted);
          padding: 0 var(--space-1);
        }

        @media (max-width: 600px) {
          .recipe-pagination {
            flex-direction: column;
            align-items: center;
          }
        }
      `}</style>
    </nav>
  );
};

