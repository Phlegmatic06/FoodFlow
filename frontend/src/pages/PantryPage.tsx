import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { plannerClient } from '../api/plannerClient';
import { PantryItem, UpdatePantryItemInput } from '../api/types/planner';
import {
  getOrCreateGuestSession,
  recoverExpiredGuestSession,
} from '../utils/guestSession';
import { PantryAddIngredient } from '../components/pantry/PantryAddIngredient';
import { PantryInventoryList } from '../components/pantry/PantryInventoryList';
import { PantryRecipeMatcher } from '../components/pantry/PantryRecipeMatcher';

export const PantryPage: React.FC = () => {
  const [sessionId, setSessionId] = useState<string>('');
  const [items, setItems] = useState<PantryItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isMutating, setIsMutating] = useState<boolean>(false);
  const [pantryError, setPantryError] = useState<string | null>(null);

  // Initialize guest session and fetch inventory
  const fetchPantry = useCallback(async () => {
    setIsLoading(true);
    setPantryError(null);

    try {
      const activeSessionId = await getOrCreateGuestSession();
      setSessionId(activeSessionId);

      const response = await plannerClient.getPantry(activeSessionId);
      setItems(response.items || []);
    } catch (err: unknown) {
      // Check for session expired (401)
      const isExpired =
        (err as { statusCode?: number })?.statusCode === 401 ||
        (err as { status?: number })?.status === 401 ||
        /session_expired|expired/i.test(err instanceof Error ? err.message : '');

      if (isExpired) {
        try {
          const freshSessionId = await recoverExpiredGuestSession();
          setSessionId(freshSessionId);
          const response = await plannerClient.getPantry(freshSessionId);
          setItems(response.items || []);
          return;
        } catch {
          // Recovery failed
        }
      }

      setPantryError(
        err instanceof Error ? err.message : 'Failed to query pantry inventory from service'
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPantry();
  }, [fetchPantry]);

  // Existing canonical IDs in pantry for duplicate prevention
  const existingCanonicalIds = useMemo(() => {
    const ids = new Set<number>();
    items.forEach((it) => {
      if (it.canonical_ingredient_id !== null && it.canonical_ingredient_id !== undefined) {
        ids.add(it.canonical_ingredient_id);
      }
    });
    return ids;
  }, [items]);

  // Add ingredient: append to current inventory and call PUT /api/v1/pantry
  const handleAddIngredient = useCallback(
    async (newItem: UpdatePantryItemInput) => {
      setIsMutating(true);
      setPantryError(null);

      const activeSessionId = sessionId || (await getOrCreateGuestSession());
      setSessionId(activeSessionId);

      // Whole-inventory replacement: take current items + new item
      const updatedPayload: UpdatePantryItemInput[] = [
        ...items.map((it) => ({
          raw_name: it.raw_name,
          canonical_ingredient_id: it.canonical_ingredient_id,
        })),
        newItem,
      ];

      try {
        const response = await plannerClient.updatePantry(updatedPayload, activeSessionId);
        setItems(response.items || []);
      } catch (err: unknown) {
        const isExpired =
          (err as { statusCode?: number })?.statusCode === 401 ||
          (err as { status?: number })?.status === 401;

        if (isExpired) {
          const freshSessionId = await recoverExpiredGuestSession();
          setSessionId(freshSessionId);
          const response = await plannerClient.updatePantry(updatedPayload, freshSessionId);
          setItems(response.items || []);
          return;
        }
        throw err;
      } finally {
        setIsMutating(false);
      }
    },
    [items, sessionId]
  );

  // Remove ingredient: filter out item and call PUT /api/v1/pantry
  const handleRemoveItem = useCallback(
    async (itemId: number) => {
      setIsMutating(true);
      setPantryError(null);

      const activeSessionId = sessionId || (await getOrCreateGuestSession());
      setSessionId(activeSessionId);

      const remainingPayload: UpdatePantryItemInput[] = items
        .filter((it) => it.id !== itemId)
        .map((it) => ({
          raw_name: it.raw_name,
          canonical_ingredient_id: it.canonical_ingredient_id,
        }));

      try {
        const response = await plannerClient.updatePantry(remainingPayload, activeSessionId);
        setItems(response.items || []);
      } catch (err: unknown) {
        const isExpired =
          (err as { statusCode?: number })?.statusCode === 401 ||
          (err as { status?: number })?.status === 401;

        if (isExpired) {
          const freshSessionId = await recoverExpiredGuestSession();
          setSessionId(freshSessionId);
          const response = await plannerClient.updatePantry(remainingPayload, freshSessionId);
          setItems(response.items || []);
          return;
        }
        setPantryError(
          err instanceof Error
            ? `Failed to remove ingredient: ${err.message}`
            : 'Failed to remove ingredient from pantry.'
        );
      } finally {
        setIsMutating(false);
      }
    },
    [items, sessionId]
  );

  // Clear entire pantry: call PUT /api/v1/pantry with []
  const handleClearAll = useCallback(async () => {
    setIsMutating(true);
    setPantryError(null);

    const activeSessionId = sessionId || (await getOrCreateGuestSession());
    setSessionId(activeSessionId);

    try {
      const response = await plannerClient.updatePantry([], activeSessionId);
      setItems(response.items || []);
    } catch (err: unknown) {
      const isExpired =
        (err as { statusCode?: number })?.statusCode === 401 ||
        (err as { status?: number })?.status === 401;

      if (isExpired) {
        const freshSessionId = await recoverExpiredGuestSession();
        setSessionId(freshSessionId);
        const response = await plannerClient.updatePantry([], freshSessionId);
        setItems(response.items || []);
        return;
      }
      setPantryError(
        err instanceof Error
          ? `Failed to clear pantry: ${err.message}`
          : 'Failed to clear pantry inventory.'
      );
    } finally {
      setIsMutating(false);
    }
  }, [sessionId]);

  return (
    <div className="container page-container pantry-page" data-testid="pantry-page">
      {/* 1. Header Section */}
      <header className="page-header">
        <span className="editorial-badge">Recommendation &amp; Planner Service :8003</span>
        <h1 className="page-title">Pantry Inventory &amp; Ingredient Matching</h1>
        <p className="page-lead">
          Manage household ingredients and discover recipes optimized for minimal culinary waste
          using the NutriPod canonical ingredient taxonomy.
        </p>
      </header>

      {/* 2. Main Workspace: Add Ingredient & Active Inventory */}
      <div className="pantry-workspace-grid">
        <section className="add-column" aria-label="Add Ingredient to Pantry">
          <PantryAddIngredient
            onAddIngredient={handleAddIngredient}
            isSubmitting={isMutating}
            existingCanonicalIds={existingCanonicalIds}
          />
        </section>

        <section className="inventory-column" aria-label="Current Pantry Inventory">
          <PantryInventoryList
            items={items}
            isLoading={isLoading}
            error={pantryError}
            onRemoveItem={handleRemoveItem}
            onClearAll={handleClearAll}
            onRetry={fetchPantry}
            isMutating={isMutating}
          />
        </section>
      </div>

      {/* 3. Recipe Overlap Matching Engine Section */}
      <PantryRecipeMatcher
        pantryItemCount={items.length}
        sessionId={sessionId}
        onSessionExpired={recoverExpiredGuestSession}
      />

      {/* 4. Architecture & Session Info Cards */}
      <div className="page-grid spec-grid">
        <div className="editorial-card info-card">
          <h2 className="card-heading">Zero-Waste Matching Engine</h2>
          <p className="card-body-text">
            The planner matching algorithm reconciles user pantry items against recipe ingredient lists:
          </p>
          <ul className="spec-list">
            <li>
              <strong>Canonical Resolution:</strong> Normalizes variations (e.g. &ldquo;chicken breast&rdquo; &rarr; &ldquo;chicken&rdquo;) via the 106-canonical taxonomy.
            </li>
            <li>
              <strong>Pantry Staple Handling:</strong> Configurable exclusion of common staples (salt, pepper, water) from matching denominators.
            </li>
            <li>
              <strong>Match Percentage:</strong> Computes exact coverage ratio and ranks viable recipes by pantry overlap.
            </li>
            <li>
              <strong>Missing Ingredients:</strong> Identifies remaining items for automated grocery list generation.
            </li>
          </ul>
        </div>

        <div className="editorial-card info-card">
          <h2 className="card-heading">Guest Session Security &amp; Isolation</h2>
          <p className="card-body-text">
            Pantry inventories are persisted under temporary or persistent guest sessions:
          </p>
          <ul className="spec-list">
            <li>
              <strong>Header Isolation:</strong> Enforces the <code>X-Guest-Session-ID</code> UUID header exclusively on port 8003.
            </li>
            <li>
              <strong>Cross-Guest Protection:</strong> Strict database isolation prevents access to other guest sessions.
            </li>
            <li>
              <strong>Zero Registration Friction:</strong> Immediate usage without requiring credential sign-up.
            </li>
          </ul>
        </div>
      </div>

      <style>{`
        .pantry-page {
          padding-top: var(--space-8);
          padding-bottom: var(--space-16);
          display: flex;
          flex-direction: column;
          gap: var(--space-8);
        }

        .page-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          border-bottom: 2px solid var(--color-border-strong);
          padding-bottom: var(--space-6);
        }

        .page-title {
          font-family: var(--font-serif);
          font-size: var(--text-3xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .page-lead {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
          max-width: 820px;
          line-height: 1.6;
        }

        .pantry-workspace-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: var(--space-8);
          align-items: start;
        }

        @media (min-width: 992px) {
          .pantry-workspace-grid {
            grid-template-columns: 1fr 1.3fr;
          }
        }

        .spec-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
          gap: var(--space-6);
        }

        .info-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-6);
        }

        .card-heading {
          font-family: var(--font-serif);
          font-size: var(--text-xl);
          font-weight: 700;
          color: var(--color-text-primary);
        }

        .card-body-text {
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
          line-height: 1.5;
        }

        .spec-list {
          list-style: square;
          padding-left: var(--space-5);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          font-size: var(--text-sm);
          color: var(--color-text-secondary);
        }

        .spec-list strong {
          color: var(--color-text-primary);
        }
      `}</style>
    </div>
  );
};
