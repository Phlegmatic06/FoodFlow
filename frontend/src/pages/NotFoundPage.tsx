import React from 'react';
import { Link } from 'react-router-dom';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="container not-found-container">
      <div className="editorial-card not-found-card">
        <span className="editorial-badge">HTTP 404</span>
        <h1 className="not-found-title">Page Not Found</h1>
        <p className="not-found-text">
          The requested culinary route or resource does not exist within the NutriPod platform catalog.
        </p>
        <div className="not-found-actions">
          <Link to="/" className="btn btn-primary">
            Return to Home
          </Link>
          <Link to="/recipes" className="btn btn-secondary">
            Browse Recipes
          </Link>
        </div>
      </div>

      <style>{`
        .not-found-container {
          padding-top: var(--space-16);
          padding-bottom: var(--space-16);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .not-found-card {
          max-width: 560px;
          width: 100%;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: var(--space-4);
          background-color: var(--color-surface);
          border: 1px solid var(--color-border);
          padding: var(--space-8);
        }

        .not-found-title {
          font-size: var(--text-3xl);
          font-weight: 700;
        }

        .not-found-text {
          font-size: var(--text-base);
          color: var(--color-text-secondary);
          line-height: 1.6;
        }

        .not-found-actions {
          display: flex;
          flex-wrap: wrap;
          gap: var(--space-3);
          margin-top: var(--space-2);
        }
      `}</style>
    </div>
  );
};

