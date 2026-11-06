import React from 'react';
import { Link } from 'react-router-dom';
import { RecipeDetail } from '../../api/types/recipe';

interface RecipeDetailHeaderProps {
  recipe: RecipeDetail;
  onEnterCookingMode?: () => void;
  hasInstructions: boolean;
}

export const RecipeDetailHeader: React.FC<RecipeDetailHeaderProps> = ({
  recipe,
  onEnterCookingMode,
  hasInstructions,
}) => {
  // Format ratings honestly: unrated or missing must never display as 0 stars
  const hasRating =
    recipe.rating_average !== null &&
    recipe.rating_average !== undefined &&
    recipe.rating_count > 0;

  const ratingText = hasRating
    ? `★ ${recipe.rating_average!.toFixed(1)} (${recipe.rating_count} ${
        recipe.rating_count === 1 ? 'review' : 'reviews'
      })`
    : 'Rating unavailable';

  // Format time honestly: 0 or missing must never display as 0 mins
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
    <header className="recipe-detail-header" data-testid="recipe-detail-header">
      {/* Breadcrumb Navigation */}
      <nav aria-label="Breadcrumb" className="breadcrumb-nav">
        <ol className="breadcrumb-list">
          <li className="breadcrumb-item">
            <Link to="/" className="breadcrumb-link">Home</Link>
          </li>
          <li className="breadcrumb-separator" aria-hidden="true">&gt;</li>
          <li className="breadcrumb-item">
            <Link to="/recipes" className="breadcrumb-link">Recipes</Link>
          </li>
          <li className="breadcrumb-separator" aria-hidden="true">&gt;</li>
          <li className="breadcrumb-item breadcrumb-current" aria-current="page">
            {recipe.title}
          </li>
        </ol>
      </nav>

      {/* Badges Bar */}
      <div className="header-badges">
        <span className="editorial-badge dataset-badge" data-testid="recipe-dataset-badge">
          {datasetLabel}
        </span>
        {recipe.cuisine && (
          <span className="editorial-badge cuisine-badge" data-testid="recipe-cuisine-badge">
            {recipe.cuisine}
          </span>
        )}
        {recipe.servings !== null && recipe.servings !== undefined && recipe.servings > 0 && (
          <span className="editorial-badge servings-badge" data-testid="recipe-servings-badge">
            Serves {recipe.servings}
          </span>
        )}
      </div>

      {/* Main Title */}
      <h1 className="recipe-detail-title" data-testid="recipe-detail-title">
        {recipe.title}
      </h1>

      {/* Description if present */}
      {recipe.description && (
        <p className="recipe-detail-description" data-testid="recipe-detail-description">
          {recipe.description}
        </p>
      )}

      {/* Telemetry Row */}
      <div className="recipe-telemetry-strip" data-testid="recipe-telemetry-strip">
        <div
          className={`telemetry-pill ${!hasRating ? 'telemetry-unavailable' : ''}`}
          data-testid="recipe-rating-pill"
        >
          <span className="telemetry-label">Rating:</span>
          <span className="telemetry-value">{ratingText}</span>
        </div>

        <div
          className={`telemetry-pill ${!hasTime ? 'telemetry-unavailable' : ''}`}
          data-testid="recipe-time-pill"
        >
          <span className="telemetry-label">Total Time:</span>
          <span className="telemetry-value">{timeText}</span>
        </div>

        {recipe.prep_time_minutes !== null &&
          recipe.prep_time_minutes !== undefined &&
          recipe.prep_time_minutes > 0 && (
            <div className="telemetry-pill" data-testid="recipe-prep-pill">
              <span className="telemetry-label">Prep:</span>
              <span className="telemetry-value">{formatTime(recipe.prep_time_minutes)}</span>
            </div>
          )}

        {recipe.cook_time_minutes !== null &&
          recipe.cook_time_minutes !== undefined &&
          recipe.cook_time_minutes > 0 && (
            <div className="telemetry-pill" data-testid="recipe-cook-pill">
              <span className="telemetry-label">Cook:</span>
              <span className="telemetry-value">{formatTime(recipe.cook_time_minutes)}</span>
            </div>
          )}

        {recipe.submitted_date && (
          <div className="telemetry-pill" data-testid="recipe-submitted-pill">
            <span className="telemetry-label">Date:</span>
            <span className="telemetry-value">{recipe.submitted_date}</span>
          </div>
        )}
      </div>

      {/* Tags Row */}
      {recipe.tags && recipe.tags.length > 0 && (
        <div className="recipe-tags-list" aria-label="Recipe Tags" data-testid="recipe-tags-list">
          {recipe.tags.map((tag) => (
            <span key={tag} className="editorial-badge recipe-tag-item">
              #{tag}
            </span>
          ))}
        </div>
      )}

      {/* Actions Row */}
      <div className="header-actions">
        {hasInstructions && onEnterCookingMode && (
          <button
            type="button"
            className="btn btn-primary enter-cooking-btn"
            onClick={onEnterCookingMode}
            data-testid="enter-cooking-mode-btn"
          >
            Start Cooking Mode &rarr;
          </button>
        )}

        {recipe.source_url && (
          <a
            href={recipe.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary source-link-btn"
            data-testid="recipe-source-url"
          >
            View Original Dataset Record &#8599;
          </a>
        )}
      </div>

      <style>{`
        .recipe-detail-header {
          display: flex;
          flex-direction: column;
          gap: var(--space-4);
          padding-bottom: var(--space-6);
          border-bottom: 2px solid var(--color-border);
        }

        .breadcrumb-nav {
          font-size: var(--text-xs);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .breadcrumb-list {
          display: flex;
          list-style: none;
          gap: var(--space-2);
          align-items: center;
          flex-wrap: wrap;
        }

        .breadcrumb-link {
          color: var(--color-text-muted);
        }

        .breadcrumb-link:hover {
          color: var(--color-accent);
        }

        .breadcrumb-separator {
          color: var(--color-border-strong);
        }

        .breadcrumb-current {
          color: var(--color-text-primary);
          font-weight: 600;
          max-width: 400px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .header-badges {
          display: flex;
          gap: var(--space-2);
          align-items: center;
          flex-wrap: wrap;
        }

        .dataset-badge {
          background-color: var(--color-secondary-subtle);
          color: var(--color-secondary-accent);
          border-color: var(--color-secondary-accent);
        }

        .cuisine-badge {
          background-color: var(--color-surface-subtle);
          color: var(--color-text-secondary);
        }

        .servings-badge {
          background-color: var(--color-accent-subtle);
          color: var(--color-accent);
        }

        .recipe-detail-title {
          font-size: var(--text-3xl);
          font-weight: 700;
          line-height: 1.15;
          color: var(--color-text-primary);
          letter-spacing: -0.02em;
        }

        .recipe-detail-description {
          font-size: var(--text-base);
          line-height: 1.6;
          color: var(--color-text-secondary);
          max-width: 800px;
        }

        .recipe-telemetry-strip {
          display: flex;
          gap: var(--space-3);
          flex-wrap: wrap;
          align-items: center;
        }

        .telemetry-pill {
          display: inline-flex;
          align-items: center;
          gap: var(--space-1);
          padding: var(--space-1) var(--space-3);
          font-size: var(--text-xs);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
        }

        .telemetry-unavailable {
          color: var(--color-text-muted);
          font-style: italic;
        }

        .telemetry-label {
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
          color: var(--color-text-muted);
        }

        .telemetry-value {
          color: var(--color-text-primary);
          font-weight: 500;
        }

        .telemetry-unavailable .telemetry-value {
          color: var(--color-text-muted);
        }

        .recipe-tags-list {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-2);
        }

        .recipe-tag-item {
          background-color: var(--color-surface-subtle);
          color: var(--color-text-secondary);
          border-color: var(--color-border);
          font-size: var(--text-xs);
        }

        .header-actions {
          display: flex;
          gap: var(--space-3);
          flex-wrap: wrap;
          margin-top: var(--space-2);
        }

        .enter-cooking-btn {
          font-size: var(--text-sm);
        }

        .source-link-btn {
          font-size: var(--text-sm);
        }

        @media (min-width: 768px) {
          .recipe-detail-title {
            font-size: var(--text-4xl);
          }
        }
      `}</style>
    </header>
  );
};

