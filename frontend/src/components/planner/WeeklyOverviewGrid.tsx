import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { CookingStatus, MealPlanDetail, MealPlanSlotDetail } from '../../api/types/planner';

interface WeeklyOverviewGridProps {
  plan: MealPlanDetail;
  onUpdateCookingStatus: (slotId: number, status: CookingStatus) => Promise<void>;
  onRemoveSlot: (slotId: number) => Promise<void>;
  onDeletePlan: () => Promise<void>;
  onStartNewPlan: () => void;
  isMutating: boolean;
}

export const WeeklyOverviewGrid: React.FC<WeeklyOverviewGridProps> = ({
  plan,
  onUpdateCookingStatus,
  onRemoveSlot,
  onDeletePlan,
  onStartNewPlan,
  isMutating,
}) => {
  const [selectedDayIndex, setSelectedDayIndex] = useState<number | 'all'>('all');
  const [confirmDelete, setConfirmDelete] = useState<boolean>(false);
  const [updatingSlotId, setUpdatingSlotId] = useState<number | null>(null);

  // Group slots by day_index
  const daysMap = new Map<number, MealPlanSlotDetail[]>();
  for (let i = 0; i < plan.days; i++) {
    daysMap.set(i, []);
  }
  plan.slots.forEach((slot) => {
    const list = daysMap.get(slot.day_index) || [];
    list.push(slot);
    daysMap.set(slot.day_index, list);
  });

  const handleStatusChange = async (slotId: number, status: CookingStatus) => {
    setUpdatingSlotId(slotId);
    try {
      await onUpdateCookingStatus(slotId, status);
    } finally {
      setUpdatingSlotId(null);
    }
  };

  const handleRemove = async (slotId: number) => {
    setUpdatingSlotId(slotId);
    try {
      await onRemoveSlot(slotId);
    } finally {
      setUpdatingSlotId(null);
    }
  };

  const handleDeleteClick = async () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    await onDeletePlan();
  };

  // Cooking stats
  const totalSlots = plan.slots.length;
  const cookedCount = plan.slots.filter((s) => s.cooking_status === 'cooked').length;
  const skippedCount = plan.slots.filter((s) => s.cooking_status === 'skipped').length;
  const pendingCount = plan.slots.filter((s) => s.cooking_status === 'pending').length;
  const cookedPct = totalSlots > 0 ? Math.round((cookedCount / totalSlots) * 100) : 0;

  const visibleDayIndices =
    selectedDayIndex === 'all'
      ? Array.from(daysMap.keys()).sort((a, b) => a - b)
      : [selectedDayIndex];

  return (
    <div className="editorial-card weekly-overview-card" data-testid="weekly-overview-card">
      {/* 1. Plan Header Strip */}
      <div className="overview-header-strip">
        <div className="plan-identity">
          <span className="editorial-badge">Active Weekly Schedule</span>
          <h2 className="plan-title" data-testid="plan-title">
            {plan.name}
          </h2>
          <div className="plan-meta-tags">
            <span className="plan-tag" data-testid="plan-days-tag">
              {plan.days} Days Horizon
            </span>
            {plan.target_calories_kcal && (
              <span className="plan-tag" data-testid="plan-calories-tag">
                Target: {plan.target_calories_kcal} kcal/day
              </span>
            )}
            <span className="plan-tag date-tag">
              Saved {new Date(plan.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>

        <div className="plan-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onStartNewPlan}
            disabled={isMutating}
            data-testid="start-new-plan-btn"
          >
            Create Another Plan
          </button>
          <button
            type="button"
            className={`btn btn-secondary btn-delete-plan ${confirmDelete ? 'btn-confirm-delete' : ''}`}
            onClick={handleDeleteClick}
            disabled={isMutating}
            data-testid="delete-plan-btn"
          >
            {confirmDelete ? 'Click to Confirm Delete' : 'Delete Plan'}
          </button>
          {confirmDelete && (
            <button
              type="button"
              className="btn btn-secondary btn-cancel-delete"
              onClick={() => setConfirmDelete(false)}
              data-testid="cancel-delete-plan-btn"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* 2. Cooking Progress Banner */}
      <div className="cooking-progress-summary" data-testid="cooking-progress-summary">
        <div className="progress-labels">
          <span className="progress-title">Weekly Cooking Execution Progress</span>
          <span className="progress-stats" data-testid="cooking-stats-label">
            {cookedCount} of {totalSlots} Meals Prepared ({cookedPct}%)
          </span>
        </div>
        <div
          className="progress-bar-track"
          role="progressbar"
          aria-valuenow={cookedPct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Weekly cooking progress"
        >
          <div className="progress-bar-fill" style={{ width: `${cookedPct}%` }} />
        </div>
        <div className="progress-badges-row">
          <span className="progress-badge badge-pending">
            Pending: {pendingCount}
          </span>
          <span className="progress-badge badge-cooked">
            Cooked: {cookedCount}
          </span>
          <span className="progress-badge badge-skipped">
            Skipped: {skippedCount}
          </span>
        </div>
      </div>

      {/* 3. Day Navigation Tabs (Ensures usability on mobile & desktop) */}
      <nav aria-label="Day filter" className="day-tabs-container">
        <button
          type="button"
          className={`day-tab ${selectedDayIndex === 'all' ? 'active-day-tab' : ''}`}
          onClick={() => setSelectedDayIndex('all')}
          data-testid="day-tab-all"
        >
          All Days ({plan.days})
        </button>
        {Array.from(daysMap.keys())
          .sort((a, b) => a - b)
          .map((dIdx) => (
            <button
              key={dIdx}
              type="button"
              className={`day-tab ${selectedDayIndex === dIdx ? 'active-day-tab' : ''}`}
              onClick={() => setSelectedDayIndex(dIdx)}
              data-testid={`day-tab-${dIdx}`}
            >
              Day {dIdx + 1}
            </button>
          ))}
      </nav>

      {/* 4. Days Grid */}
      <div className="days-columns-container" data-testid="days-columns-container">
        {visibleDayIndices.map((dayIdx) => {
          const slots = daysMap.get(dayIdx) || [];

          return (
            <div
              key={dayIdx}
              className="day-schedule-card"
              data-testid={`day-card-${dayIdx}`}
            >
              <div className="day-schedule-header">
                <h3 className="day-schedule-title">Day {dayIdx + 1}</h3>
                <span className="day-slots-count">
                  {slots.length} {slots.length === 1 ? 'Meal' : 'Meals'}
                </span>
              </div>

              {slots.length === 0 ? (
                <div className="empty-day-state" data-testid={`empty-day-${dayIdx}`}>
                  <p>No meals scheduled for Day {dayIdx + 1}.</p>
                </div>
              ) : (
                <div className="day-slots-list">
                  {slots.map((slot) => {
                    const isSlotBusy = updatingSlotId === slot.id || isMutating;
                    const statusClass = `status-${slot.cooking_status}`;

                    return (
                      <div
                        key={slot.id}
                        className={`meal-slot-item ${statusClass}`}
                        data-testid={`slot-item-${slot.id}`}
                      >
                        <div className="slot-item-header">
                          <span
                            className="slot-type-pill"
                            data-testid={`slot-type-${slot.id}`}
                          >
                            {slot.slot_type.toUpperCase()}
                          </span>
                          <span
                            className={`cooking-status-pill ${statusClass}`}
                            data-testid={`cooking-status-pill-${slot.id}`}
                          >
                            {slot.cooking_status === 'cooked'
                              ? 'Cooked'
                              : slot.cooking_status === 'skipped'
                              ? 'Skipped'
                              : 'Pending'}
                          </span>
                        </div>

                        <h4
                          className="slot-recipe-name"
                          data-testid={`slot-recipe-name-${slot.id}`}
                        >
                          {slot.recipe_title}
                        </h4>

                        {/* Cooking Mode & Details Links */}
                        <div className="slot-links-row">
                          <Link
                            to={`/recipes/${encodeURIComponent(slot.recipe_id)}`}
                            className="slot-link recipe-details-link"
                            data-testid={`recipe-link-${slot.id}`}
                          >
                            View Recipe &rarr;
                          </Link>
                          <Link
                            to={`/recipes/${encodeURIComponent(slot.recipe_id)}?mode=cook`}
                            className="slot-link cook-mode-link"
                            data-testid={`cook-mode-link-${slot.id}`}
                          >
                            Cooking Mode 👨‍🍳
                          </Link>
                        </div>

                        {/* Interactive Cooking Execution Controls */}
                        <div className="slot-progress-actions">
                          {slot.cooking_status !== 'cooked' && (
                            <button
                              type="button"
                              className="btn btn-progress btn-mark-cooked"
                              onClick={() => handleStatusChange(slot.id, 'cooked')}
                              disabled={isSlotBusy}
                              data-testid={`mark-cooked-btn-${slot.id}`}
                              aria-label={`Mark ${slot.recipe_title} as cooked`}
                            >
                              ✓ Cooked
                            </button>
                          )}

                          {slot.cooking_status !== 'skipped' && (
                            <button
                              type="button"
                              className="btn btn-progress btn-mark-skipped"
                              onClick={() => handleStatusChange(slot.id, 'skipped')}
                              disabled={isSlotBusy}
                              data-testid={`mark-skipped-btn-${slot.id}`}
                              aria-label={`Mark ${slot.recipe_title} as skipped`}
                            >
                              ⤫ Skip
                            </button>
                          )}

                          {slot.cooking_status !== 'pending' && (
                            <button
                              type="button"
                              className="btn btn-progress btn-mark-pending"
                              onClick={() => handleStatusChange(slot.id, 'pending')}
                              disabled={isSlotBusy}
                              data-testid={`mark-pending-btn-${slot.id}`}
                              aria-label={`Reset ${slot.recipe_title} to pending`}
                            >
                              Reset
                            </button>
                          )}

                          <button
                            type="button"
                            className="btn btn-progress btn-remove-slot"
                            onClick={() => handleRemove(slot.id)}
                            disabled={isSlotBusy}
                            data-testid={`remove-slot-btn-${slot.id}`}
                            aria-label={`Remove ${slot.recipe_title} from schedule`}
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <style>{`
        .weekly-overview-card {
          display: flex;
          flex-direction: column;
          gap: var(--space-6);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          padding: var(--space-6);
        }

        .overview-header-strip {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          flex-wrap: wrap;
          gap: var(--space-4);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-5);
        }

        .plan-identity {
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .plan-title {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
          margin: 0;
        }

        .plan-meta-tags {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
        }

        .plan-tag {
          font-size: var(--text-xs);
          padding: 0.2rem 0.5rem;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          font-weight: 500;
        }

        .date-tag {
          color: var(--color-text-secondary);
        }

        .plan-actions {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
        }

        .btn-delete-plan {
          color: #b91c1c;
          border-color: #b91c1c;
        }

        .btn-confirm-delete {
          background-color: #b91c1c !important;
          color: #ffffff !important;
          border-color: #b91c1c !important;
        }

        .cooking-progress-summary {
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
          letter-spacing: 0.03em;
        }

        .progress-stats {
          font-weight: 700;
        }

        .progress-bar-track {
          height: 10px;
          background-color: var(--color-bg);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          overflow: hidden;
        }

        .progress-bar-fill {
          height: 100%;
          background-color: #16a34a;
          transition: width 0.3s ease;
        }

        .progress-badges-row {
          display: flex;
          gap: var(--space-3);
          font-size: var(--text-xs);
        }

        .progress-badge {
          padding: 0.15rem 0.4rem;
          border-radius: 0px !important;
          font-weight: 600;
        }

        .badge-pending {
          background: rgba(100, 116, 139, 0.15);
          color: var(--color-text-secondary);
        }

        .badge-cooked {
          background: rgba(22, 163, 74, 0.15);
          color: #15803d;
        }

        .badge-skipped {
          background: rgba(217, 119, 6, 0.15);
          color: #b45309;
        }

        .day-tabs-container {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-3);
        }

        .day-tab {
          padding: 0.4rem 0.8rem;
          font-size: var(--text-xs);
          font-weight: 600;
          background: var(--color-surface);
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          cursor: pointer;
          color: var(--color-text);
        }

        .day-tab.active-day-tab {
          background: var(--color-text);
          color: var(--color-bg);
          border-color: var(--color-text);
        }

        .days-columns-container {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: var(--space-4);
        }

        .day-schedule-card {
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          background: var(--color-surface);
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .day-schedule-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 1px solid var(--color-border);
          padding-bottom: var(--space-2);
        }

        .day-schedule-title {
          font-family: var(--font-serif);
          font-size: var(--text-lg);
          margin: 0;
        }

        .day-slots-count {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .day-slots-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-3);
        }

        .meal-slot-item {
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          background: var(--color-bg);
          padding: var(--space-3);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
        }

        .meal-slot-item.status-cooked {
          border-left: 4px solid #16a34a;
        }

        .meal-slot-item.status-skipped {
          border-left: 4px solid #d97706;
          opacity: 0.75;
        }

        .slot-item-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .slot-type-pill {
          font-size: 10px;
          letter-spacing: 0.08em;
          font-weight: 700;
          color: var(--color-text-secondary);
        }

        .cooking-status-pill {
          font-size: 10px;
          font-weight: 700;
          padding: 0.1rem 0.4rem;
          border-radius: 0px !important;
          text-transform: uppercase;
        }

        .cooking-status-pill.status-pending {
          background: var(--color-surface);
          color: var(--color-text-secondary);
          border: 1px solid var(--color-border);
        }

        .cooking-status-pill.status-cooked {
          background: #16a34a;
          color: #ffffff;
        }

        .cooking-status-pill.status-skipped {
          background: #d97706;
          color: #ffffff;
        }

        .slot-recipe-name {
          font-size: var(--text-sm);
          font-weight: 600;
          margin: 0;
          line-height: 1.35;
        }

        .slot-links-row {
          display: flex;
          gap: var(--space-3);
          font-size: var(--text-xs);
          margin-top: 0.2rem;
        }

        .slot-link {
          text-decoration: underline;
          color: var(--color-text);
          font-weight: 500;
        }

        .slot-link:hover {
          color: var(--color-accent, #c2410c);
        }

        .slot-progress-actions {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-1);
          margin-top: var(--space-2);
          border-top: 1px solid var(--color-border);
          padding-top: var(--space-2);
        }

        .btn-progress {
          font-size: 11px;
          padding: 0.2rem 0.5rem;
          border: 1px solid var(--color-border);
          border-radius: 0px !important;
          background: var(--color-surface);
          cursor: pointer;
        }

        .btn-progress:hover:not(:disabled) {
          background: var(--color-bg);
        }

        .btn-mark-cooked {
          color: #15803d;
          font-weight: 600;
        }

        .btn-mark-skipped {
          color: #b45309;
        }

        .btn-remove-slot {
          color: #b91c1c;
          margin-left: auto;
        }

        .empty-day-state {
          padding: var(--space-4);
          text-align: center;
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }
      `}</style>
    </div>
  );
};

