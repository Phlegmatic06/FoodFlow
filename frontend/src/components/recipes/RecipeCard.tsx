import React from 'react';
import { Link } from 'react-router-dom';
import { RecipeSummary } from '../../api/types/recipe';

interface RecipeCardProps {
  recipe: RecipeSummary;
}

export const RecipeCard: React.FC<RecipeCardProps> = ({ recipe }) => {
  // Format ratings honestly
  const hasRating = recipe.rating_average !== null && recipe.rating_average !== undefined;
  const ratingText = hasRating
    ? `★ ${recipe.rating_average!.toFixed(1)} (${recipe.rating_count} ${
        recipe.rating_count === 1 ? 'review' : 'reviews'
      })`
    : 'Rating unavailable';

  // Format time honestly
  const hasTime =
    recipe.total_time_minutes !== null &&
    recipe.total_time_minutes !== undefined &&
    recipe.total_time_minutes > 0;

  const formatTime = (minutes: number) => {
    if (minutes < 60) return `${minutes} mins`;
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
  };

  const timeText = hasTime ? formatTime(recipe.total_time_minutes!) : 'Time unavailable';

  const datasetLabel = recipe.source_dataset === 'food_com' ? 'Food.com' : 'RecipeNLG';

  return (
    <article className="editorial-card recipe-card" data-testid={`recipe-card-${recipe.id}`}>
      {/* Neutral Minimalist Header Placeholder */}
      <div className="card-visual-header">
        <div className="visual-monogram" aria-hidden="true">
          <span>{recipe.title.charAt(0).toUpperCase()}</span>
        </div>
        <div className="visual-badges">
          <span className="editorial-badge dataset-badge">{datasetLabel}</span>
          {recipe.cuisine && (
            <span className="editorial-badge cuisine-badge">{recipe.cuisine}</span>
          )}
        </div>
      </div>

      <div className="card-content">
        <h3 className="recipe-card-title">
          <Link to={`/recipes/${recipe.id}`} className="recipe-title-link">
            {recipe.title}
          </Link>
        </h3>

        {/* Telemetry Row: Rating & Total Time */}
        <div className="recipe-telemetry-row">
          <span
            className={`telemetry-item rating-item ${!hasRating ? 'telemetry-unavailable' : ''}`}
            data-testid="recipe-rating"
          >
            {ratingText}
          </span>
          <span className="telemetry-separator" aria-hidden="true">
            •
          </span>
          <span
            className={`telemetry-item time-item ${!hasTime ? 'telemetry-unavailable' : ''}`}
            data-testid="recipe-time"
          >
            {timeText}
          </span>
        </div>

        {/* Excerpt Description if available */}
        {recipe.description && (
          <p className="recipe-card-description">{recipe.description}</p>
        )}

        {/* Tag Preview Chips */}
        {recipe.tag_preview && recipe.tag_preview.length > 0 && (
          <div className="recipe-card-tags" aria-label="Recipe tags">
            {recipe.tag_preview.slice(0, 4).map((tag, idx) => (
              <span key={`${tag}-${idx}`} className="tag-chip">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="card-footer-action">
        <Link to={`/recipes/${recipe.id}`} className="card-action-link">
          View Recipe &rarr;
        </Link>
      </div>

      <style>{`
        .recipe-card {
          display: flex;
          flex-direction: column;
          height: 100%;
          padding: 0;
          border: 1px solid var(--color-border);
          background-color: var(--color-surface);
          transition: border-color var(--transition-fast), transform var(--transition-fast);
        }

        .recipe-card:hover {
          border-color: var(--color-border-strong);
        }

        .card-visual-header {
          height: 80px;
          background-color: var(--color-surface-subtle);
          border-bottom: 1px solid var(--color-border);
          padding: var(--space-3) var(--space-4);
          display: flex;
          align-items: center;
          justify-content: space-between;
          position: relative;
        }

        .visual-monogram {
          font-family: var(--font-serif);
          font-size: var(--text-2xl);
          font-weight: 700;
          color: var(--color-border-strong);
          user-select: none;
        }

        .visual-badges {
          display: flex;
          gap: var(--space-2);
          flex-wrap: wrap;
        }

        .dataset-badge {
          font-size: 0.65rem;
          padding: 0.1rem 0.4rem;
        }

        .cuisine-badge {
          font-size: 0.65rem;
          padding: 0.1rem 0.4rem;
          background-color: var(--color-secondary-subtle);
          color: var(--color-secondary-accent);
        }

        .card-content {
          padding: var(--space-4);
          display: flex;
          flex-direction: column;
          gap: var(--space-2);
          flex: 1;
        }

        .recipe-card-title {
          font-size: var(--text-lg);
          font-family: var(--font-serif);
          line-height: 1.25;
          margin-bottom: var(--space-1);
        }

        .recipe-title-link {
          color: var(--color-text-primary);
          text-decoration: none;
        }

        .recipe-title-link:hover {
          color: var(--color-accent);
        }

        .recipe-telemetry-row {
          display: flex;
          align-items: center;
          gap: var(--space-2);
          font-family: var(--font-sans);
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
        }

        .telemetry-item {
          font-weight: 500;
        }

        .telemetry-unavailable {
          color: var(--color-text-muted);
          font-style: italic;
        }

        .telemetry-separator {
          color: var(--color-border-strong);
        }

        .rating-item {
          color: var(--color-accent);
        }

        .rating-item.telemetry-unavailable {
          color: var(--color-text-muted);
        }

        .recipe-card-description {
          font-size: var(--text-xs);
          color: var(--color-text-secondary);
          line-height: 1.5;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          margin-top: var(--space-1);
        }

        .recipe-card-tags {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-1);
          margin-top: auto;
          padding-top: var(--space-2);
        }

        .tag-chip {
          display: inline-block;
          font-size: 0.65rem;
          font-family: var(--font-sans);
          background-color: var(--color-surface-subtle);
          color: var(--color-text-muted);
          padding: 0.1rem 0.35rem;
          border: 1px solid var(--color-border);
          text-transform: lowercase;
        }

        .card-footer-action {
          border-top: 1px solid var(--color-border);
          padding: var(--space-2) var(--space-4);
          background-color: var(--color-surface);
        }

        .card-action-link {
          font-size: var(--text-xs);
          font-weight: 600;
          color: var(--color-accent);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .card-action-link:hover {
          color: var(--color-accent-hover);
        }
      `}</style>
    </article>
  );
};

