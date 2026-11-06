import React, { useState } from 'react';
import { PantryItem } from '../../api/types/planner';

interface PantryInventoryListProps {
  items: PantryItem[];
  isLoading: boolean;
  error: string | null;
  onRemoveItem: (itemId: number) => Promise<void>;
  onClearAll: () => Promise<void>;
  onRetry: () => void;
  isMutating: boolean;
}

export const PantryInventoryList: React.FC<PantryInventoryListProps> = ({
  items,
  isLoading,
  error,
  onRemoveItem,
  onClearAll,
  onRetry,
  isMutating,
}) => {
  const [confirmClear, setConfirmClear] = useState<boolean>(false);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const handleRemove = async (id: number) => {
    setRemovingId(id);
    try {
      await onRemoveItem(id);
    } finally {
      setRemovingId(null);
    }
  };

  const handleClear = async () => {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    try {
      await onClearAll();
      setConfirmClear(false);
    } catch {
      // error handled at page level
    }
  };

  return (
    <div className="editorial-card inventory-card" data-testid="pantry-inventory-card">
      <div className="inventory-header-strip">
        <div className="title-with-count">
          <span className="editorial-badge">Active Inventory</span>
          <h2 className="inventory-heading" data-testid="inventory-heading">
            Current Pantry Items
          </h2>
          <span className="count-badge" data-testid="inventory-count-badge">
            {items.length} {items.length === 1 ? 'Item' : 'Items'}
          </span>
        </div>

        {items.length > 0 && (
          <div className="inventory-header-actions">
            <button
              type="button"
              className={`btn btn-secondary btn-clear-all ${confirmClear ? 'btn-confirm-active' : ''}`}
              onClick={handleClear}
              disabled={isMutating}
              data-testid="clear-all-pantry-btn"
            >
              {confirmClear ? 'Click again to confirm clear' : 'Clear Entire Pantry'}
            </button>
            {confirmClear && (
              <button
                type="button"
                className="btn btn-secondary btn-cancel-clear"
                onClick={() => setConfirmClear(false)}
                data-testid="cancel-clear-btn"
              >
                Cancel
              </button>
            )}
          </div>
        )}
      </div>

      {isLoading ? (
        <div className="inventory-status-box loading-box" data-testid="pantry-loading">
          <p>Querying Recommendation &amp; Planner Service (:8003) for session pantry...</p>
        </div>
      ) : (
        <>
          {error && (
            <div className="inventory-status-box error-box" role="alert" data-testid="pantry-error">
              <span className="editorial-badge error-badge">Pantry Service Notice</span>
              <p className="error-msg">{error}</p>
              <button
                type="button"
                className="btn btn-secondary btn-retry"
                onClick={onRetry}
                data-testid="pantry-retry-btn"
              >
                Retry Connection
              </button>
            </div>
          )}

          {items.length === 0 && !error ? (
            <div className="inventory-empty-state" data-testid="pantry-empty-state">
              <span className="editorial-badge empty-badge">Empty Inventory</span>
              <h3 className="empty-title">Your Pantry is Empty</h3>
              <p className="empty-desc">
                You haven&apos;t added any ingredients to this guest session yet. Search and add items
                above from our verified canonical taxonomy to track your home inventory and find recipes
                you can cook right now.
              </p>
            </div>
          ) : (
            items.length > 0 && (
              <ul className="inventory-items-grid" data-testid="pantry-items-list">
                {items.map((item) => {
                  const isItemRemoving = removingId === item.id;

                  return (
                    <li
                      key={item.id}
                      className={`inventory-item-card ${isItemRemoving ? 'removing' : ''}`}
                      data-testid={`pantry-item-${item.id}`}
                    >
                      <div className="item-details">
                        <div className="item-name-row">
                          <span className="item-raw-name" data-testid={`item-name-${item.id}`}>
                            {item.raw_name}
                          </span>
                          {item.canonical_ingredient_id !== null && item.canonical_ingredient_id !== undefined && (
                            <span className="canonical-id-badge" data-testid={`item-canonical-${item.id}`}>
                              Canonical #{item.canonical_ingredient_id}
                            </span>
                          )}
                        </div>
                        {item.created_at && (
                          <span className="item-added-date">
                            Added: {new Date(item.created_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>

                      <div className="item-actions">
                        <button
                          type="button"
                          className="btn btn-secondary btn-remove-item"
                          onClick={() => handleRemove(item.id)}
                          disabled={isMutating}
                          data-testid={`remove-item-${item.id}`}
                          aria-label={`Remove ${item.raw_name} from pantry`}
                          title={`Remove ${item.raw_name}`}
                        >
                          {isItemRemoving ? 'Removing...' : 'Remove'}
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )
          )}
        </>
      )}

      <style>{`
        .inventory-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-6);
        }

        .inventory-header-strip {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-wrap: wrap;
          gap: var(--space-3);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-3);
        }

        .title-with-count {
          display: flex;
          align-items: center;
          gap: var(--space-3);
          flex-wrap: wrap;
        }

        .inventory-heading {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .count-badge {
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border-strong);
          font-size: var(--text-xs);
          font-weight: 700;
          padding: 2px var(--space-2);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .inventory-header-actions {
          display: flex;
          gap: var(--space-2);
          align-items: center;
        }

        .btn-clear-all {
          font-size: var(--text-xs);
          padding: var(--space-1) var(--space-3);
        }

        .btn-confirm-active {
          border-color: var(--color-error);
          color: var(--color-error);
          font-weight: 700;
        }

        .btn-cancel-clear {
          font-size: var(--text-xs);
          padding: var(--space-1) var(--space-2);
        }

        .inventory-status-box {
          padding: var(--space-6);
          border: 1px solid var(--color-border);
          background-color: var(--color-surface-subtle);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
          align-items: flex-start;
          font-size: var(--text-sm);
        }

        .error-box {
          border-color: var(--color-error);
        }

        .error-badge {
          background-color: var(--color-error-subtle);
          color: var(--color-error);
          border-color: var(--color-error);
        }

        .error-msg {
          color: var(--color-text-primary);
          font-weight: 500;
        }

        .inventory-empty-state {
          padding: var(--space-8);
          background-color: var(--color-surface-subtle);
          border: 1px dashed var(--color-border-strong);
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: var(--space-3);
          max-width: 650px;
          margin: var(--space-4) auto;
        }

        .empty-title {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .empty-desc {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          line-height: 1.6;
        }

        .inventory-items-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-3);
          list-style: none;
          margin: 0;
          padding: 0;
        }

        @media (min-width: 640px) {
          .inventory-items-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (min-width: 1024px) {
          .inventory-items-grid {
            grid-template-columns: repeat(3, 1fr);
          }
        }

        .inventory-item-card {
          background-color: var(--color-surface-subtle);
          border: 1px solid var(--color-border);
          padding: var(--space-4);
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: var(--space-3);
          transition: border-color 0.15s ease;
        }

        .inventory-item-card:hover {
          border-color: var(--color-border-strong);
        }

        .inventory-item-card.removing {
          opacity: 0.5;
        }

        .item-details {
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
          overflow: hidden;
        }

        .item-name-row {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          flex-wrap: wrap;
        }

        .item-raw-name {
          font-size: var(--text-sm);
          font-weight: 700;
          color: var(--color-text-primary);
          word-break: break-word;
        }

        .canonical-id-badge {
          font-size: 10px;
          font-family: var(--font-mono);
          font-weight: 700;
          color: var(--color-accent);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: 1px 4px;
        }

        .item-added-date {
          font-size: var(--text-xs);
          color: var(--color-text-muted);
        }

        .btn-remove-item {
          font-size: var(--text-xs);
          padding: var(--space-1) var(--space-2);
          white-space: nowrap;
        }

        .btn-remove-item:hover {
          color: var(--color-error);
          border-color: var(--color-error);
        }
      `}</style>
    </div>
  );
};

