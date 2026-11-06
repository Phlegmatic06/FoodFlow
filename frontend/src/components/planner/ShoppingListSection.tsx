import React, { useState } from 'react';
import { ShoppingListItem, ShoppingListResponse } from '../../api/types/planner';

interface ShoppingListSectionProps {
  shoppingList: ShoppingListResponse | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onToggleItem: (itemId: number, checked: boolean) => Promise<void>;
  isMutating: boolean;
}

export const ShoppingListSection: React.FC<ShoppingListSectionProps> = ({
  shoppingList,
  isLoading,
  error,
  onRetry,
  onToggleItem,
  isMutating,
}) => {
  const [filter, setFilter] = useState<'all' | 'remaining' | 'purchased'>('all');
  const [togglingId, setTogglingId] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="editorial-card shopping-card" data-testid="shopping-list-loading">
        <span className="editorial-badge">Aggregating Grocery Requirements</span>
        <p className="loading-text">
          Querying Recipe and Planner services to consolidate recipe ingredients across scheduled meals...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="editorial-card shopping-card error-card" role="alert" data-testid="shopping-list-error">
        <span className="editorial-badge error-badge">Shopping List Unavailable</span>
        <p className="error-text">{error}</p>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onRetry}
          data-testid="shopping-retry-btn"
        >
          Retry Shopping List
        </button>
      </div>
    );
  }

  if (!shoppingList) {
    return null;
  }

  // Calculate totals across categories
  const allItems: ShoppingListItem[] = [];
  shoppingList.categories.forEach((cat) => {
    cat.items.forEach((item) => allItems.push(item));
  });

  const totalCount = allItems.length;
  const purchasedCount = allItems.filter((it) => it.checked).length;
  const remainingCount = totalCount - purchasedCount;
  const completionPct = totalCount > 0 ? Math.round((purchasedCount / totalCount) * 100) : 0;

  const handleCheckboxClick = async (item: ShoppingListItem) => {
    setTogglingId(item.id);
    try {
      await onToggleItem(item.id, !item.checked);
    } finally {
      setTogglingId(null);
    }
  };

  return (
    <div className="editorial-card shopping-card" data-testid="shopping-list-section">
      {/* 1. Header & Progress */}
      <div className="shopping-header">
        <div className="title-area">
          <span className="editorial-badge">Consolidated Grocery Checklist</span>
          <h2 className="shopping-title" data-testid="shopping-list-heading">
            Consolidated Grocery Shopping List
          </h2>
          <p className="shopping-lead">
            Aggregated ingredient requirements across all planned recipes, grouped by supermarket aisle.
          </p>
        </div>

        {/* Pantry Behavior Disclosure */}
        <div className="pantry-notice-box" data-testid="pantry-behavior-notice">
          <span className="editorial-badge notice-badge">Pantry Notice</span>
          <p className="notice-text">
            <strong>Pantry Integration Behavior:</strong> The shopping list consolidates all required recipe ingredients
            across your scheduled meals. It does not automatically subtract pantry inventory from item quantities;
            please review your pantry before purchasing.
          </p>
        </div>
      </div>

      {/* 2. Progress Tracker */}
      <div className="shopping-progress-bar-card" data-testid="shopping-progress-card">
        <div className="progress-labels">
          <span className="progress-title">Checklist Procurement Status</span>
          <span className="progress-numbers" data-testid="shopping-stats-label">
            {purchasedCount} of {totalCount} Items Acquired ({completionPct}%)
          </span>
        </div>
        <div
          className="progress-track"
          role="progressbar"
          aria-valuenow={completionPct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Shopping checklist completion"
        >
          <div className="progress-fill" style={{ width: `${completionPct}%` }} />
        </div>

        {/* Filter Tabs */}
        <div className="filter-buttons-row">
          <button
            type="button"
            className={`filter-btn ${filter === 'all' ? 'active-filter' : ''}`}
            onClick={() => setFilter('all')}
            data-testid="filter-all-btn"
          >
            All Items ({totalCount})
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'remaining' ? 'active-filter' : ''}`}
            onClick={() => setFilter('remaining')}
            data-testid="filter-remaining-btn"
          >
            Remaining ({remainingCount})
          </button>
          <button
            type="button"
            className={`filter-btn ${filter === 'purchased' ? 'active-filter' : ''}`}
            onClick={() => setFilter('purchased')}
            data-testid="filter-purchased-btn"
          >
            Purchased ({purchasedCount})
          </button>
        </div>
      </div>

      {/* 3. Aisle Categories */}
      {totalCount === 0 ? (
        <div className="empty-shopping-state" data-testid="empty-shopping-state">
          <p>No grocery items required for this meal plan.</p>
        </div>
      ) : (
        <div className="aisle-categories-container" data-testid="aisle-categories-container">
          {shoppingList.categories.map((categoryGroup) => {
            const filteredItems = categoryGroup.items.filter((item) => {
              if (filter === 'remaining') return !item.checked;
              if (filter === 'purchased') return item.checked;
              return true;
            });

            if (filteredItems.length === 0) return null;

            return (
              <div
                key={categoryGroup.category}
                className="aisle-group-card"
                data-testid={`aisle-group-${categoryGroup.category.toLowerCase().replace(/[^a-z0-9]/g, '-')}`}
              >
                <div className="aisle-header">
                  <h3 className="aisle-title">{categoryGroup.category}</h3>
                  <span className="aisle-count">
                    {filteredItems.length} {filteredItems.length === 1 ? 'Item' : 'Items'}
                  </span>
                </div>

                <ul className="shopping-items-list" role="list">
                  {filteredItems.map((item) => {
                    const isBusy = togglingId === item.id || isMutating;

                    return (
                      <li
                        key={item.id}
                        className={`shopping-item-row ${item.checked ? 'item-checked' : ''}`}
                        data-testid={`shopping-item-${item.id}`}
                      >
                        <label className="item-checkbox-label">
                          <input
                            type="checkbox"
                            checked={item.checked}
                            onChange={() => handleCheckboxClick(item)}
                            disabled={isBusy}
                            className="item-checkbox"
                            data-testid={`shopping-item-checkbox-${item.id}`}
                            aria-label={`Mark ${item.ingredient_name} as ${item.checked ? 'unpurchased' : 'purchased'}`}
                          />
                          <span
                            className="item-name"
                            data-testid={`shopping-item-name-${item.id}`}
                          >
                            {item.ingredient_name}
                          </span>
                        </label>

                        {item.quantity_display && (
                          <span
                            className="item-quantity-badge"
                            data-testid={`shopping-item-qty-${item.id}`}
                          >
                            {item.quantity_display}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      )}

      <style>{`
        .shopping-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          padding: var(--space-6);
        }

        .shopping-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-5);
        }

        .shopping-title {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
          margin: 0;
        }

        .shopping-lead {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          margin: var(--space-1) 0 0 0;
        }

        .pantry-notice-box {
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          border-left: 4px solid var(--color-text);
          border-radius: 0px !important;
          padding: var(--space-3) var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-1);
        }

        .notice-badge {
          background: var(--color-text);
          color: var(--color-bg);
          align-self: flex-start;
          font-size: 10px;
        }

        .notice-text {
          font-size: var(--text-xs);
          color: var(--color-text);
          margin: 0;
          line-height: 1.4;
        }

        .shopping-progress-bar-card {
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .progress-labels {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: var(--text-sm);
        }

        .progress-title {
          font-weight: 600;
        }

        .progress-numbers {
          font-weight: 700;
        }

        .progress-track {
          height: 10px;
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          background: #16a34a;
          transition: width 0.3s ease;
        }

        .filter-buttons-row {
          display: flex;
          gap: var(--space-2);
          margin-top: var(--space-1);
        }

        .filter-btn {
          font-size: var(--text-xs);
          font-weight: 600;
          padding: 0.3rem 0.7rem;
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          cursor: pointer;
          color: var(--color-text);
        }

        .filter-btn.active-filter {
          background: var(--color-text);
          color: var(--color-bg);
          border-color: var(--color-text);
        }

        .aisle-categories-container {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
          gap: var(--space-5);
        }

        .aisle-group-card {
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          background: var(--color-surface);
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .aisle-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-2);
        }

        .aisle-title {
          font-family: var(--font-serif);
          font-size: var(--text-base);
          font-weight: 700;
          margin: 0;
        }

        .aisle-count {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .shopping-items-list {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .shopping-item-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--space-2) var(--space-3);
          background: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          gap: var(--space-2);
        }

        .shopping-item-row.item-checked {
          opacity: 0.6;
          background: var(--color-surface);
        }

        .item-checkbox-label {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          cursor: pointer;
          font-size: var(--text-sm);
        }

        .item-checkbox {
          border-radius: 0px !important;
          cursor: pointer;
        }

        .item-name {
          font-weight: 500;
        }

        .shopping-item-row.item-checked .item-name {
          text-decoration: line-through;
          color: var(--color-text-secondary);
        }

        .item-quantity-badge {
          font-size: var(--text-xs);
          padding: 0.15rem 0.4rem;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          font-weight: 600;
          white-space: nowrap;
        }

        .empty-shopping-state {
          padding: var(--space-8);
          text-align: center;
          color: var(--color-text-secondary);
          font-size: var(--text-sm);
        }
      `}</style>
    </div>
  );
};

